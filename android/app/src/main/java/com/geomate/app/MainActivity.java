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

    /** 最近一次后端启动异常（Java 侧），供页面展示定位。 */
    private static volatile String lastBackendError = "";

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
        // 暴露后端启动错误给 H5 页面（登录页可展示真实错误信息）
        webView.addJavascriptInterface(new JsNativeBridge(), "AndroidNative");
        webView.loadUrl("file:///android_asset/www/pages/login.html");

        startBackendServer();
    }

    /** Java→JS 桥：H5 页面通过 window.AndroidNative.getBackendError() 读取后端启动错误。 */
    private class JsNativeBridge {
        @android.webkit.JavascriptInterface
        public String getBackendError() {
            String javaErr = lastBackendError;
            try {
                com.chaquo.python.Python py = ensurePython();
                String pyErr = py.getModule("android_bridge").callAttr("get_last_error").toString();
                if (pyErr != null && !pyErr.trim().isEmpty()) return pyErr.trim();
            } catch (Exception e) {
                if (javaErr == null || javaErr.isEmpty()) javaErr = "python bridge: " + e;
            }
            return javaErr == null ? "" : javaErr;
        }
    }

    /** 获取 Chaquopy Python 实例；未初始化时手动初始化（Chaquopy 文档推荐方式，避免 PyApplication 启动即崩溃）。 */
    private com.chaquo.python.Python ensurePython() {
        if (!com.chaquo.python.Python.isStarted()) {
            com.chaquo.python.Python.start(new com.chaquo.python.android.AndroidPlatform(this));
        }
        return com.chaquo.python.Python.getInstance();
    }

    /** 在后台线程启动内嵌 Python 后端服务（非阻塞）。 */
    private void startBackendServer() {
        new Thread(() -> {
            try {
                com.chaquo.python.Python py = ensurePython();
                py.getModule("android_bridge").callAttr("start_server_async");
                Log.i(TAG, "内嵌后端已在后台启动");
            } catch (Exception e) {
                lastBackendError = e.toString();
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
