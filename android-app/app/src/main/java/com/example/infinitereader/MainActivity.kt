package com.example.infinitereader

import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import com.example.infinitereader.theme.InfiniteReaderTheme

class MainActivity : ComponentActivity() {
    private var ttsBridge: TTSBridge? = null
    private var webView: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1001)
            }
        }

        setContent {
            InfiniteReaderTheme {
                Surface(
                    modifier = Modifier
                        .fillMaxSize()
                        .systemBarsPadding(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    AndroidView(
                        factory = { ctx ->
                            WebView(ctx).apply {
                                webView = this
                                settings.javaScriptEnabled = true
                                settings.domStorageEnabled = true
                                settings.allowFileAccess = true
                                settings.allowContentAccess = true
                                settings.allowUniversalAccessFromFileURLs = true
                                settings.allowFileAccessFromFileURLs = true
                                settings.useWideViewPort = true
                                settings.loadWithOverviewMode = false
                                settings.cacheMode = WebSettings.LOAD_DEFAULT

                                val bridge = TTSBridge(this@MainActivity, this)
                                ttsBridge = bridge
                                addJavascriptInterface(bridge, "AndroidTTS")

                                webViewClient = WebViewClient()
                                webChromeClient = WebChromeClient()
                                loadUrl("file:///android_asset/reader.html")
                            }
                        },
                        modifier = Modifier.fillMaxSize()
                    )
                }
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        val wv = webView
        if (wv != null) {
            wv.evaluateJavascript(
                "(function() { " +
                "  var active = document.querySelector('.drawer-overlay.active'); " +
                "  if (active) { " +
                "    if (window.closeAllDrawers) { window.closeAllDrawers(); } " +
                "    else { active.classList.remove('active'); } " +
                "    return true; " +
                "  } " +
                "  return false; " +
                "})()"
            ) { result ->
                if (result != "true") {
                    super.onBackPressed()
                }
            }
        } else {
            super.onBackPressed()
        }
    }

    override fun onResume() {
        super.onResume()
        ttsBridge?.syncToWebView()
    }

    override fun onDestroy() {
        super.onDestroy()
        ttsBridge?.shutdown()
    }
}
