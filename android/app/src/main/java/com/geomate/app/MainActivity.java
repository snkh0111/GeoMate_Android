package com.geomate.app;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * GeoMate Android 主界面。
 *
 * 1. 加载内嵌 H5 登录页（assets/www/pages/login.html）
 * 2. 在后台线程通过 Chaquopy 启动内嵌 FastAPI 服务（127.0.0.1:8000）
 *
 * 前端页面通过 http://127.0.0.1:8000 访问后端接口。
 */
public class MainActivity extends Activity {

    private static final String TAG = "GeoMate";
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webview);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(true);
        // 禁止通过 file:// 访问外部（保持安全）
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);

        webView.setWebViewClient(new WebViewClient());
        webView.loadUrl("file:///android_asset/www/pages/login.html");

        startBackendServer();
    }

    /** 在后台线程启动内嵌 Python 后端服务（非阻塞）。 */
    private void startBackendServer() {
        new Thread(() -> {
            try {
                com.chaquo.python.Python py = com.chaquo.python.Python.getInstance();
                py.getModule("android_bridge").callAttr("start_server_async");
                Log.i(TAG, "内嵌后端已在后台启动");
            } catch (Exception e) {
                Log.e(TAG, "启动内嵌后端失败", e);
            }
        }, "GeoMate-Backend").start();
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
