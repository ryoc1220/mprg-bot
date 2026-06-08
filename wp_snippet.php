<?php
/**
 * MPRG 論文自動登録 カスタム REST API エンドポイント
 *
 * エンドポイント①: POST /wp-json/mprg/v1/publication   (論文メタデータ登録)
 * エンドポイント②: POST /wp-json/mprg/v1/upload-pdf    (PDF ファイルアップロード)
 *
 * 【設計の肝】
 * Toolset Types は wp_postmeta テーブルに "wpcf-" プレフィックス付きで
 * データを保存している。WordPress 標準の REST API meta 経由では
 * Toolset 独自の検証が介入するため書き込みに失敗するが、
 * PHP から直接 update_post_meta() を呼べば Toolset 編集画面にも
 * 正しく反映される（Toolset は wpcf- postmeta をそのまま読む）。
 */

add_action( 'rest_api_init', function () {

    // ── ① 論文メタデータ登録 ──────────────────────────────────────────
    register_rest_route( 'mprg/v1', '/publication', array(
        'methods'             => 'POST',
        'callback'            => 'mprg_create_publication',
        'permission_callback' => function () {
            return current_user_can( 'edit_posts' );
        },
    ) );

    // ── ② PDF アップロード ────────────────────────────────────────────
    register_rest_route( 'mprg/v1', '/upload-pdf', array(
        'methods'             => 'POST',
        'callback'            => 'mprg_upload_pdf',
        'permission_callback' => function () {
            return current_user_can( 'edit_posts' );
        },
    ) );

} );


function mprg_create_publication( WP_REST_Request $request ) {

    $params = $request->get_json_params();

    // ── バリデーション ──────────────────────────────────────────────
    if ( empty( $params['title'] ) ) {
        return new WP_Error(
            'missing_title',
            'タイトルが必要です',
            array( 'status' => 400 )
        );
    }

    // ── 1. 投稿の作成（draft）──────────────────────────────────────
    $publication_date     = sanitize_text_field( $params['publication_date'] ?? current_time( 'mysql' ) );
    $publication_date_gmt = get_gmt_from_date( $publication_date );

    $post_data = array(
        'post_title'    => sanitize_text_field( $params['title'] ),
        'post_content'  => wp_kses_post( $params['abstract'] ?? '' ),
        'post_status'   => 'draft',
        'post_type'     => 'publications',
        'post_name'     => sanitize_text_field( $params['slug'] ?? '' ),
        'post_date'     => $publication_date,
        'post_date_gmt' => $publication_date_gmt,
    );

    $post_id = wp_insert_post( $post_data, true );

    if ( is_wp_error( $post_id ) ) {
        return new WP_Error(
            'post_creation_failed',
            $post_id->get_error_message(),
            array( 'status' => 500 )
        );
    }

    // ── 2. Toolset カスタムフィールドの直接書き込み ────────────────
    $toolset_fields = array(
        'wpcf-author'        => $params['wpcf-author']        ?? '',
        'wpcf-publication'   => $params['wpcf-publication']   ?? '',
        'wpcf-tex_ref'       => $params['wpcf-tex_ref']       ?? '',
        'wpcf-bibtex_ref'    => $params['wpcf-bibtex_ref']    ?? '',
        'wpcf-dlfile1'       => $params['wpcf-dlfile1']       ?? '',
        'wpcf-linktxt1'      => $params['wpcf-linktxt1']      ?? '',
        'wpcf-subtxt1'       => $params['wpcf-subtxt1']       ?? '',
        'wpcf-category_type' => $params['wpcf-category_type'] ?? '',
        'wpcf-paper_type'    => $params['wpcf-paper_type']    ?? '',
        'wpcf-lang-ja'       => $params['wpcf-lang-ja']       ?? '0',
        'wpcf-lang-en'       => $params['wpcf-lang-en']       ?? '0',
    );

    foreach ( $toolset_fields as $meta_key => $meta_value ) {
        update_post_meta( $post_id, $meta_key, $meta_value );
    }

    // ── 3. レスポンス ──────────────────────────────────────────────
    $edit_link = admin_url( "post.php?post={$post_id}&action=edit" );

    return new WP_REST_Response( array(
        'success'   => true,
        'post_id'   => $post_id,
        'edit_link' => $edit_link,
        'slug'      => get_post_field( 'post_name', $post_id ),
    ), 201 );
}


/**
 * PDF アップロードエンドポイント
 *
 * POST /wp-json/mprg/v1/upload-pdf
 *   multipart/form-data:
 *     pdf   : PDFファイル
 *     slug  : 識別子（例: F20260513_hazumi）
 *     group : グループフォルダ名（例: F_group）
 *
 * 保存先: {webroot}/data/MPRG/{group}/{slug}.pdf
 * WordPress が /wp/ サブディレクトリにあるため ABSPATH の親をwebroot とみなす
 */
function mprg_upload_pdf( WP_REST_Request $request ) {

    $files = $request->get_file_params();

    if ( empty( $files['pdf'] ) || $files['pdf']['error'] !== UPLOAD_ERR_OK ) {
        $err_code = $files['pdf']['error'] ?? 'none';
        return new WP_Error(
            'no_pdf',
            "PDFファイルが見つかりません（error: {$err_code}）",
            array( 'status' => 400 )
        );
    }

    $slug  = sanitize_file_name( $request->get_param( 'slug' ) );
    $group = sanitize_text_field( $request->get_param( 'group' ) );

    // セキュリティ: group は "{1文字大文字}_group" の形式のみ許可
    if ( ! preg_match( '/^[A-Z]_group$/', $group ) ) {
        return new WP_Error(
            'invalid_group',
            "groupパラメータが不正です: {$group}",
            array( 'status' => 400 )
        );
    }

    // WebRoot = WordPress（/wp/）の親ディレクトリ
    $web_root   = realpath( ABSPATH . '..' );
    $upload_dir = "{$web_root}/data/MPRG/{$group}/";

    if ( ! is_dir( $upload_dir ) ) {
        if ( ! mkdir( $upload_dir, 0755, true ) ) {
            return new WP_Error(
                'mkdir_failed',
                "ディレクトリ作成失敗: {$upload_dir}",
                array( 'status' => 500 )
            );
        }
    }

    $dest = $upload_dir . $slug . '.pdf';

    if ( ! move_uploaded_file( $files['pdf']['tmp_name'], $dest ) ) {
        return new WP_Error(
            'save_failed',
            "ファイル保存失敗: {$dest}",
            array( 'status' => 500 )
        );
    }

    $url = "http://mprg.jp/data/MPRG/{$group}/{$slug}.pdf";

    return new WP_REST_Response( array(
        'success' => true,
        'url'     => $url,
        'path'    => $dest,
    ), 200 );
}
