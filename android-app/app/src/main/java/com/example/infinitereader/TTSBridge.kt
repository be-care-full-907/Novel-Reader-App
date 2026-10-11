package com.example.infinitereader

import android.content.Context
import android.os.Bundle
import android.os.PowerManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

class TTSBridge(private val context: Context, private val webView: WebView) : TextToSpeech.OnInitListener {
    private var tts: TextToSpeech? = null
    private var isInitialized = false
    private var wakeLock: PowerManager.WakeLock? = null

    init {
        tts = TextToSpeech(context, this)
        try {
            val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
            wakeLock = pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "InfiniteReader:TTSWakeLock")
            wakeLock?.setReferenceCounted(false)
        } catch (e: Exception) {
            Log.e("TTSBridge", "Failed to create wakeLock: ${e.message}")
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            isInitialized = true
            tts?.language = Locale.US
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    val id = utteranceId?.toIntOrNull() ?: 0
                    webView.post {
                        webView.evaluateJavascript("window.onSpeechStart && window.onSpeechStart($id);", null)
                    }
                }

                override fun onDone(utteranceId: String?) {
                    val id = utteranceId?.toIntOrNull() ?: 0
                    webView.post {
                        webView.evaluateJavascript("window.onSpeechDone && window.onSpeechDone($id);", null)
                    }
                }

                override fun onRangeStart(utteranceId: String?, start: Int, end: Int, frame: Int) {
                    val id = utteranceId?.toIntOrNull() ?: 0
                    webView.post {
                        webView.evaluateJavascript("window.onWordBoundary && window.onWordBoundary($id, $start, $end);", null)
                    }
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    val id = utteranceId?.toIntOrNull() ?: 0
                    webView.post {
                        webView.evaluateJavascript("window.onSpeechDone && window.onSpeechDone($id);", null)
                    }
                }
            })

            // Notify JavaScript that native voices are initialized and ready
            webView.post {
                webView.evaluateJavascript("window.onVoicesLoaded && window.onVoicesLoaded();", null)
            }
        } else {
            Log.e("TTSBridge", "TextToSpeech init failed with status: $status")
        }
    }

    @JavascriptInterface
    fun speak(text: String, sentenceId: Int) {
        if (!isInitialized) return
        try {
            if (wakeLock?.isHeld == false) {
                wakeLock?.acquire(15 * 60 * 1000L) // 15 mins max safety timeout
            }
        } catch (e: Exception) {
            Log.e("TTSBridge", "Error acquiring wakeLock: ${e.message}")
        }
        val params = Bundle()
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, params, sentenceId.toString())
    }

    @JavascriptInterface
    fun stop() {
        tts?.stop()
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
            }
        } catch (e: Exception) {
            Log.e("TTSBridge", "Error releasing wakeLock: ${e.message}")
        }
    }

    @JavascriptInterface
    fun setRate(rate: Float) {
        tts?.setSpeechRate(rate)
    }

    @JavascriptInterface
    fun setPitch(pitch: Float) {
        tts?.setPitch(pitch)
    }

    @JavascriptInterface
    fun setVoice(voiceName: String): Boolean {
        val voiceList = tts?.voices
        if (voiceList != null) {
            val matchedVoice = voiceList.find { it.name == voiceName }
            if (matchedVoice != null) {
                tts?.voice = matchedVoice
                tts?.language = matchedVoice.locale
                Log.d("TTSBridge", "Successfully set voice to: $voiceName (${matchedVoice.locale})")
                return true
            }
        }
        return false
    }

    @JavascriptInterface
    fun getVoicesJson(): String {
        val array = JSONArray()
        val voices = tts?.voices
        if (voices != null) {
            // Sort so english and natural voices are prioritized
            val sortedVoices = voices.sortedWith(compareBy({ it.locale.language != "en" }, { it.name }))
            for (v in sortedVoices) {
                val obj = JSONObject()
                obj.put("name", v.name)
                obj.put("locale", "${v.locale.displayLanguage} (${v.locale.country})")
                obj.put("isNetwork", v.isNetworkConnectionRequired)
                array.put(obj)
            }
        }
        return array.toString()
    }

    @JavascriptInterface
    fun getNovelDataJson(): String {
        return try {
            context.assets.open("novel_data.json").bufferedReader().use { it.readText() }
        } catch (e: Exception) {
            "{}"
        }
    }

    @JavascriptInterface
    fun downloadUrl(urlStr: String): String {
        return downloadUrlWithAuth(urlStr, null)
    }

    @JavascriptInterface
    fun downloadUrlWithAuth(urlStr: String, authHeader: String?): String {
        return try {
            var currentUrl = urlStr
            var conn = java.net.URL(currentUrl).openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 15000
            conn.readTimeout = 45000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Android; Mobile)")
            conn.setRequestProperty("Accept", "application/vnd.github.raw, application/json, text/plain, */*")
            if (!authHeader.isNullOrEmpty() && (currentUrl.contains("github.com") || currentUrl.contains("githubusercontent.com"))) {
                conn.setRequestProperty("Authorization", authHeader)
            }
            conn.instanceFollowRedirects = false
            conn.connect()

            var redirectCount = 0
            while ((conn.responseCode in 301..308) && redirectCount < 5) {
                val location = conn.getHeaderField("Location") ?: break
                conn.disconnect()
                currentUrl = location
                conn = java.net.URL(currentUrl).openConnection() as java.net.HttpURLConnection
                conn.requestMethod = "GET"
                conn.connectTimeout = 15000
                conn.readTimeout = 45000
                conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Android; Mobile)")
                conn.setRequestProperty("Accept", "application/vnd.github.raw, application/json, text/plain, */*")
                // Only send Authorization header if target is still github.com / githubusercontent.com, NOT AWS S3!
                if (!authHeader.isNullOrEmpty() && (currentUrl.contains("github.com") || currentUrl.contains("githubusercontent.com"))) {
                    conn.setRequestProperty("Authorization", authHeader)
                }
                conn.instanceFollowRedirects = false
                conn.connect()
                redirectCount++
            }

            val code = conn.responseCode
            if (code in 200..299) {
                conn.inputStream.bufferedReader().use { it.readText() }
            } else {
                val err = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                "HTTP_ERROR:$code:$err"
            }
        } catch (e: Exception) {
            "EXCEPTION:${e.message}"
        }
    }

    @JavascriptInterface
    fun postUrl(urlStr: String, bodyJson: String, authHeader: String?): String {
        return try {
            val url = java.net.URL(urlStr)
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 15000
            conn.readTimeout = 30000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Android; Mobile)")
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.setRequestProperty("Accept", "application/vnd.github+json")
            if (!authHeader.isNullOrEmpty()) {
                conn.setRequestProperty("Authorization", authHeader)
            }
            conn.doOutput = true
            conn.outputStream.bufferedWriter().use { it.write(bodyJson) }
            conn.connect()
            val code = conn.responseCode
            if (code in 200..299) {
                val res = conn.inputStream?.bufferedReader()?.use { it.readText() } ?: ""
                if (res.isEmpty()) "SUCCESS:$code" else res
            } else {
                val err = conn.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                "HTTP_ERROR:$code:$err"
            }
        } catch (e: Exception) {
            "EXCEPTION:${e.message}"
        }
    }

    private fun getNovelBundlesDir(novelId: String): java.io.File {
        val safeNovelId = novelId.replace(Regex("[^a-zA-Z0-9._-]"), "_")
        val dir = java.io.File(context.filesDir, "downloaded_bundles_$safeNovelId")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    private val bundlesDir: java.io.File
        get() = getNovelBundlesDir("infinite-mana-in-the-apocalypse")

    @JavascriptInterface
    fun saveNovelBundle(novelId: String, fileName: String, jsonContent: String): Boolean {
        return try {
            val safeName = fileName.replace(Regex("[^a-zA-Z0-9._-]"), "_")
            val file = java.io.File(getNovelBundlesDir(novelId), safeName)
            file.writeText(jsonContent, Charsets.UTF_8)
            Log.d("TTSBridge", "Successfully saved bundle $safeName for novel $novelId (${file.length()} bytes)")
            true
        } catch (e: Exception) {
            Log.e("TTSBridge", "Failed to save bundle $fileName for novel $novelId: ${e.message}")
            false
        }
    }

    @JavascriptInterface
    fun saveBundle(fileName: String, jsonContent: String): Boolean {
        return saveNovelBundle("infinite-mana-in-the-apocalypse", fileName, jsonContent)
    }

    @JavascriptInterface
    fun getNovelBundle(novelId: String, fileName: String): String {
        return try {
            val safeName = fileName.replace(Regex("[^a-zA-Z0-9._-]"), "_")
            val file = java.io.File(getNovelBundlesDir(novelId), safeName)
            if (file.exists()) {
                file.readText(Charsets.UTF_8)
            } else {
                ""
            }
        } catch (e: Exception) {
            Log.e("TTSBridge", "Failed to read bundle $fileName for novel $novelId: ${e.message}")
            ""
        }
    }

    @JavascriptInterface
    fun getBundle(fileName: String): String {
        return getNovelBundle("infinite-mana-in-the-apocalypse", fileName)
    }

    @JavascriptInterface
    fun deleteNovelBundle(novelId: String, fileName: String): Boolean {
        return try {
            val safeName = fileName.replace(Regex("[^a-zA-Z0-9._-]"), "_")
            val file = java.io.File(getNovelBundlesDir(novelId), safeName)
            if (file.exists()) {
                val deleted = file.delete()
                Log.d("TTSBridge", "Deleted bundle $safeName for novel $novelId: $deleted")
                deleted
            } else {
                true
            }
        } catch (e: Exception) {
            Log.e("TTSBridge", "Failed to delete bundle $fileName for novel $novelId: ${e.message}")
            false
        }
    }

    @JavascriptInterface
    fun deleteBundle(fileName: String): Boolean {
        return deleteNovelBundle("infinite-mana-in-the-apocalypse", fileName)
    }

    @JavascriptInterface
    fun deleteNovelBundlesInRange(novelId: String, start: Int, end: Int): Boolean {
        return try {
            val dir = getNovelBundlesDir(novelId)
            val files = dir.listFiles { _, name -> name.endsWith(".json") }
            var anyDeleted = false
            files?.forEach { file ->
                val m = Regex("chapters_(\\d+)_(\\d+)\\.json").find(file.name)
                if (m != null) {
                    val s = m.groupValues[1].toInt()
                    val e = m.groupValues[2].toInt()
                    if (s <= end && e >= start) {
                        file.delete()
                        anyDeleted = true
                    }
                }
            }
            anyDeleted
        } catch (e: Exception) {
            Log.e("TTSBridge", "Failed to delete bundles in range $start-$end for novel $novelId: ${e.message}")
            false
        }
    }

    @JavascriptInterface
    fun deleteBundlesInRange(start: Int, end: Int): Boolean {
        return deleteNovelBundlesInRange("infinite-mana-in-the-apocalypse", start, end)
    }

    @JavascriptInterface
    fun listSavedNovelBundles(novelId: String): String {
        return try {
            val dir = getNovelBundlesDir(novelId)
            val files = dir.listFiles { _, name -> name.endsWith(".json") }
            val array = JSONArray()
            files?.forEach { file ->
                array.put(file.name)
            }
            array.toString()
        } catch (e: Exception) {
            Log.e("TTSBridge", "Failed to list saved bundles for novel $novelId: ${e.message}")
            "[]"
        }
    }

    @JavascriptInterface
    fun listSavedBundles(): String {
        return listSavedNovelBundles("infinite-mana-in-the-apocalypse")
    }

    @JavascriptInterface
    fun getNovelsCatalogJson(): String {
        return try {
            context.assets.open("novels.json").bufferedReader().use { it.readText() }
        } catch (e: Exception) {
            "[]"
        }
    }

    @JavascriptInterface
    fun getNovelDataJsonForNovel(novelId: String): String {
        val assetName = if (novelId == "infinite-mana-in-the-apocalypse") {
            "novel_data.json"
        } else {
            "${novelId.replace('-', '_')}_data.json"
        }
        return try {
            context.assets.open(assetName).bufferedReader().use { it.readText() }
        } catch (e: Exception) {
            "{}"
        }
    }

    fun shutdown() {
        tts?.stop()
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
            }
        } catch (e: Exception) {
            Log.e("TTSBridge", "Error releasing wakeLock: ${e.message}")
        }
        tts?.shutdown()
    }
}
