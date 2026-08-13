package com.geomate.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
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

    /** H5 <input type="file"> 的文件选择回调（onShowFileChooser 使用）。 */
    private ValueCallback<Uri[]> filePathCallback;
    private static final int FILE_CHOOSER_REQUEST_CODE = 100;

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

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                injectChatBarFix(view);
            }
        });
        // H5 <input type="file"> 上传依赖 onShowFileChooser；未实现时点击上传按钮无反应
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback,
                                             FileChooserParams fileChooserParams) {
                if (MainActivity.this.filePathCallback != null) {
                    MainActivity.this.filePathCallback.onReceiveValue(null);
                }
                MainActivity.this.filePathCallback = filePathCallback;
                Intent intent = fileChooserParams.createIntent();
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                try {
                    startActivityForResult(Intent.createChooser(intent, "选择 PDF 文件"),
                            FILE_CHOOSER_REQUEST_CODE);
                } catch (Exception e) {
                    MainActivity.this.filePathCallback = null;
                    return false;
                }
                return true;
            }
        });
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

    /** 修复 AI 问答页输入栏：置底 + 键盘弹起时随 WebView 上抬（不改前端源码，仅注入样式）。 */
    private void injectChatBarFix(WebView view) {
        String js = "(function(){"
            + "var inp=document.querySelector('input[placeholder*=\"输入地质问题\"]');"
            + "if(!inp)return;"
            + "var bar=inp.closest('.p-3');"
            + "if(!bar)return;"
            + "bar.style.position='fixed';"
            + "bar.style.left='0';"
            + "bar.style.right='0';"
            + "bar.style.zIndex='60';"
            + "bar.style.background='var(--gm-card,#fff)';"
            + "bar.style.boxShadow='0 -1px 0 rgba(0,0,0,.06)';"
            + "var flow=document.querySelector('.chat-flow');"
            + "if(flow)flow.style.paddingBottom='96px';"
            + "function lift(){var vv=window.visualViewport;var d=0;"
            + "if(vv){d=document.documentElement.clientHeight-vv.offsetTop-vv.height;}"
            + "bar.style.bottom=(d>0?d:0)+'px';}"
            + "lift();"
            + "if(window.visualViewport){"
            + "window.visualViewport.addEventListener('resize',lift);"
            + "window.visualViewport.addEventListener('scroll',lift);}"
            + "})();";
        view.evaluateJavascript(js, null);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER_REQUEST_CODE) {
            if (filePathCallback == null) return;
            Uri[] results = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        } else {
            super.onActivityResult(requestCode, resultCode, data);
        }
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
