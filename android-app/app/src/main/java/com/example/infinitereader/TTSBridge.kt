package com.example.infinitereader

import android.app.Activity
import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import android.util.Log
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebView
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

class TTSBridge(private val context: Context, private var webView: WebView) : TextToSpeech.OnInitListener {
    companion object {
        var activeBridgeInstance: TTSBridge? = null
    }

    private val appContext = context.applicationContext
    private var activityRef: java.lang.ref.WeakReference<Activity>? = (context as? Activity)?.let { java.lang.ref.WeakReference(it) }
    private var tts: TextToSpeech? = null
    private var isInitialized = false
    private var wakeLock: PowerManager.WakeLock? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    private var sleepRunnable: Runnable? = null
    private var chapterWatchdogRunnable: Runnable? = null

    // Native session state for unbreakable background audio playback
    private var activeSentences: List<String> = emptyList()
    private var activeSentenceIndex: Int = 0
    private var activeChapterIndex: Int = 0
    private var activeChapterTitle: String = "Chapter"
    private var activeNovelTitle: String = "Infinite Reader"
    private var activeNovelId: String = ""
    private var isPlayingActive: Boolean = false

    // Next chapter preloaded buffer for zero-delay background transitions
    private var nextChapterSentences: List<String> = emptyList()
    private var nextChapterIndex: Int = -1
    private var nextChapterTitle: String = ""

    private val activity: Activity?
        get() = activityRef?.get()

    fun updateActivity(act: Activity?, wv: WebView) {
        activityRef = act?.let { java.lang.ref.WeakReference(it) }
        this.webView = wv
    }

    fun isPlaying(): Boolean = isPlayingActive

    init {
        activeBridgeInstance = this
        tts = TextToSpeech(appContext, this)
        try {
            val pm = appContext.getSystemService(Context.POWER_SERVICE) as? PowerManager
            wakeLock = pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "InfiniteReader:TTSWakeLock")
            wakeLock?.setReferenceCounted(false)
        } catch (e: Exception) {
            Log.e("TTSBridge", "Failed to create wakeLock: ${e.message}")
        }
    }

    private fun acquireWakeLock() {
        try {
            if (wakeLock?.isHeld == false) {
                // Unlimited wakeLock while active playback continues so phone never sleeps
                wakeLock?.acquire()
                Log.d("TTSBridge", "WakeLock acquired for continuous playback")
            }
        } catch (e: Exception) {
            Log.e("TTSBridge", "Error acquiring wakeLock: ${e.message}")
        }
    }

    private fun releaseWakeLock() {
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
                Log.d("TTSBridge", "WakeLock released")
            }
        } catch (e: Exception) {
            Log.e("TTSBridge", "Error releasing wakeLock: ${e.message}")
        }
    }

    @Volatile
    var isActivityResumed: Boolean = true

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            isInitialized = true
            tts?.language = Locale.US
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    val id = utteranceId?.toIntOrNull() ?: 0
                    mainHandler.post {
                        webView.evaluateJavascript("window.onSpeechStart && window.onSpeechStart($id);", null)
                    }
                }

                override fun onDone(utteranceId: String?) {
                    val id = utteranceId?.toIntOrNull() ?: 0
                    Log.d("TTSBridge", "Utterance onDone: $id (resumed=$isActivityResumed, total=${activeSentences.size})")

                    if (!isPlayingActive) return

                    val next = id + 1
                    if (next < activeSentences.size) {
                        Log.d("TTSBridge", "Advance to sentence $next/${activeSentences.size}")
                        activeSentenceIndex = next
                        val nextText = activeSentences[next]
                        acquireWakeLock()
                        TTSPlaybackService.update(
                            appContext,
                            activeNovelTitle.ifEmpty { "Infinite Reader" },
                            "$activeChapterTitle • Sentence ${next + 1}/${activeSentences.size}",
                            true
                        )
                        val params = Bundle()
                        tts?.speak(nextText, TextToSpeech.QUEUE_FLUSH, params, next.toString())
                        mainHandler.post {
                            webView.evaluateJavascript("window.onSpeechSentenceAdvanced && window.onSpeechSentenceAdvanced($next);", null)
                        }
                    } else {
                        Log.d("TTSBridge", "Reached end of chapter $activeChapterIndex. Requesting next chapter...")
                        // 1. Notify JavaScript to load next chapter
                        mainHandler.post {
                            webView.evaluateJavascript("window.onChapterComplete && window.onChapterComplete();", null)
                        }

                        // 2. Set watchdog timer: if WebView is frozen/throttled and doesn't load next chapter within 1500ms, advance natively!
                        val expectedNext = activeChapterIndex + 1
                        chapterWatchdogRunnable?.let { mainHandler.removeCallbacks(it) }
                        val watchdog = Runnable {
                            if (isPlayingActive && activeChapterIndex < expectedNext) {
                                Log.w("TTSBridge", "Watchdog triggered: WebView delayed/frozen. Advancing natively to chapter $expectedNext!")
                                advanceToNextChapterNatively()
                            }
                        }
                        chapterWatchdogRunnable = watchdog
                        mainHandler.postDelayed(watchdog, 1500L)
                    }
                }

                override fun onRangeStart(utteranceId: String?, start: Int, end: Int, frame: Int) {
                    val id = utteranceId?.toIntOrNull() ?: 0
                    mainHandler.post {
                        webView.evaluateJavascript("window.onWordBoundary && window.onWordBoundary($id, $start, $end);", null)
                    }
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    val id = utteranceId?.toIntOrNull() ?: 0
                    mainHandler.post {
                        webView.evaluateJavascript("window.onSpeechDone && window.onSpeechDone($id);", null)
                    }
                }
            })

            // Notify JavaScript that native voices are initialized and ready
            mainHandler.post {
                webView.evaluateJavascript("window.onVoicesLoaded && window.onVoicesLoaded();", null)
            }
        } else {
            Log.e("TTSBridge", "TextToSpeech init failed with status: $status")
        }
    }

    @JavascriptInterface
    fun updatePlaybackSession(
        novelId: String,
        novelTitle: String,
        chIndex: Int,
        chTitle: String,
        sentencesJson: String,
        currentIdx: Int,
        isPlayingNow: Boolean
    ) {
        try {
            // Cancel watchdog timer since session has been successfully updated by webView
            chapterWatchdogRunnable?.let { mainHandler.removeCallbacks(it) }
            chapterWatchdogRunnable = null

            activeNovelId = novelId
            activeNovelTitle = novelTitle.ifEmpty { "Infinite Reader" }
            activeChapterIndex = chIndex
            activeChapterTitle = chTitle.ifEmpty { "Chapter ${chIndex + 1}" }
            activeSentenceIndex = currentIdx
            isPlayingActive = isPlayingNow

            val jsonArray = JSONArray(sentencesJson)
            val list = ArrayList<String>(jsonArray.length())
            for (i in 0 until jsonArray.length()) {
                list.add(jsonArray.getString(i))
            }
            activeSentences = list
            Log.d("TTSBridge", "Playback session updated: $chTitle (${activeSentences.size} sentences, start at $currentIdx, playing=$isPlayingNow)")

            if (isPlayingNow) {
                TTSPlaybackService.start(
                    appContext,
                    activeNovelTitle,
                    "$activeChapterTitle • Sentence ${currentIdx + 1}/${activeSentences.size.coerceAtLeast(1)}"
                )
            }
        } catch (e: Exception) {
            Log.e("TTSBridge", "Error updating playback session: ${e.message}")
        }
    }

    @JavascriptInterface
    fun preloadNextChapter(chIndex: Int, chTitle: String, sentencesJson: String) {
        try {
            nextChapterIndex = chIndex
            nextChapterTitle = chTitle.ifEmpty { "Chapter ${chIndex + 1}" }
            val jsonArray = JSONArray(sentencesJson)
            val list = ArrayList<String>(jsonArray.length())
            for (i in 0 until jsonArray.length()) {
                list.add(jsonArray.getString(i))
            }
            nextChapterSentences = list
            Log.d("TTSBridge", "Preloaded next chapter $chIndex ($chTitle) with ${list.size} sentences")
        } catch (e: Exception) {
            Log.e("TTSBridge", "Error preloading next chapter: ${e.message}")
        }
    }

    fun advanceToNextChapterNatively() {
        mainHandler.post {
            if (!isPlayingActive) return@post
            chapterWatchdogRunnable?.let { mainHandler.removeCallbacks(it) }
            chapterWatchdogRunnable = null

            if (nextChapterIndex == activeChapterIndex + 1 && nextChapterSentences.isNotEmpty()) {
                Log.d("TTSBridge", "Advancing natively using preloaded next chapter $nextChapterIndex ($nextChapterTitle)")
                activeChapterIndex = nextChapterIndex
                activeChapterTitle = nextChapterTitle
                activeSentences = nextChapterSentences
                activeSentenceIndex = 0

                nextChapterSentences = emptyList()
                nextChapterIndex = -1
                nextChapterTitle = ""

                acquireWakeLock()
                TTSPlaybackService.update(
                    appContext,
                    activeNovelTitle.ifEmpty { "Infinite Reader" },
                    "$activeChapterTitle • Sentence 1/${activeSentences.size.coerceAtLeast(1)}",
                    true
                )
                val params = Bundle()
                tts?.speak(activeSentences[0], TextToSpeech.QUEUE_FLUSH, params, "0")

                webView.evaluateJavascript(
                    "window.onNativeChapterAdvanced && window.onNativeChapterAdvanced($activeChapterIndex);",
                    null
                )
            } else {
                val nextChIdx = activeChapterIndex + 1
                val loaded = loadChapterFromStorage(activeNovelId, nextChIdx)
                if (loaded != null && loaded.sentences.isNotEmpty()) {
                    Log.d("TTSBridge", "Advancing natively using storage chapter $nextChIdx (${loaded.title})")
                    activeChapterIndex = nextChIdx
                    activeChapterTitle = loaded.title
                    activeSentences = loaded.sentences
                    activeSentenceIndex = 0

                    acquireWakeLock()
                    TTSPlaybackService.update(
                        appContext,
                        activeNovelTitle.ifEmpty { "Infinite Reader" },
                        "$activeChapterTitle • Sentence 1/${activeSentences.size.coerceAtLeast(1)}",
                        true
                    )
                    val params = Bundle()
                    tts?.speak(activeSentences[0], TextToSpeech.QUEUE_FLUSH, params, "0")

                    webView.evaluateJavascript(
                        "window.onNativeChapterAdvanced && window.onNativeChapterAdvanced($activeChapterIndex);",
                        null
                    )
                } else {
                    Log.d("TTSBridge", "No further chapters available natively for $activeNovelId at index $nextChIdx")
                    stop()
                }
            }
        }
    }

    private data class LoadedChapter(val title: String, val sentences: List<String>)

    private fun isMetaOrAdSentence(text: String): Boolean {
        if (text.isBlank()) return true
        val t = text.trim()
        val tl = t.lowercase()
        if (Regex("^[<\\[(]?\\s*(?:author['’s\\s]*notes?|a/?n|translator['’s\\s]*notes?|t/?n|tl['’s\\s]*notes?|editor['’s\\s]*notes?|e/?n)\\s*(?:[:\\-=–—>\\])]|$)", RegexOption.IGNORE_CASE).containsMatchIn(t)) return true
        if ((tl.contains("discord") || tl.contains("disc.gg")) && !Regex("\\b(?:sow|cause|bring|unneeded|family|civil)\\s+discord\\b", RegexOption.IGNORE_CASE).containsMatchIn(t)) {
            if (Regex("(?:https?://)?(?:www\\.)?discord\\.(?:gg|com/invite)/\\S+", RegexOption.IGNORE_CASE).containsMatchIn(t) ||
                Regex("\\b(?:join|invite to)\\s+(?:our|the|my)?\\s*discord\\b", RegexOption.IGNORE_CASE).containsMatchIn(t) ||
                Regex("\\bdiscord\\s+(?:server|link|invite)\\b", RegexOption.IGNORE_CASE).containsMatchIn(t)) return true
        }
        if (Regex("(?:https?://)?(?:www\\.)?(?:patreon\\.com|ko-fi|paypal\\.me|p[\\s.\\-_*]*a[\\s.\\-_*]*t[\\s.\\-_*]*r[\\s.\\-_*]*e[\\s.\\-_*]*o[\\s.\\-_*]*n)\\b", RegexOption.IGNORE_CASE).containsMatchIn(t) ||
            Regex("\\b(?:support\\s+(?:me|the\\s+author)|read\\s+ahead\\s+on)\\s+(?:my\\s+)?p[\\s.\\-_*]*a[\\s.\\-_*]*t[\\s.\\-_*]*r[\\s.\\-_*]*e[\\s.\\-_*]*o[\\s.\\-_*]*n\\b", RegexOption.IGNORE_CASE).containsMatchIn(t)) return true
        if (t.length < 300 && Regex("\\b(?:power\\s*stones?|golden\\s*tickets?|magic\\s*castles?|vote\\s+for\\s+(?:this|the|my)\\s+(?:book|story|novel)|don['’]?t\\s+forget\\s+to\\s+vote)\\b", RegexOption.IGNORE_CASE).containsMatchIn(t)) return true
        if (Regex("^[-—~=*#\\s]*(?:to\\s+be\\s+continued|tbc|end\\s+of\\s+chapter\\s*\\d*|thanks?\\s+for\\s+reading.*|adios|new\\s+chapter\\s+is\\s+coming\\s+soon|chapter\\s+price\\s*:\\s*\\d+\\s*coins?|if\\s+you\\s+guys\\s+haven['’]?t\\s+read\\s+all\\s+four.*)[-—~=*#\\s]*$", RegexOption.IGNORE_CASE).matches(t)) return true
        return false
    }

    private fun loadChapterFromStorage(novelId: String, chIndex: Int): LoadedChapter? {
        try {
            val dir = getNovelBundlesDir(novelId)
            val files = dir.listFiles { _, name -> name.endsWith(".json") }
            files?.forEach { file ->
                try {
                    val jsonStr = file.readText(Charsets.UTF_8)
                    val json = JSONObject(jsonStr)
                    val chapters = json.optJSONArray("chapters") ?: json.optJSONArray("bundled_chapters")
                    if (chapters != null) {
                        for (i in 0 until chapters.length()) {
                            val chObj = chapters.getJSONObject(i)
                            val idx = chObj.optInt("chapter_index", -1)
                            if (idx == chIndex || (idx == -1 && i == chIndex)) {
                                val title = chObj.optString("title", "Chapter ${chIndex + 1}")
                                val sList = ArrayList<String>()
                                val sentArr = chObj.optJSONArray("sentences")
                                if (sentArr != null && sentArr.length() > 0) {
                                    for (s in 0 until sentArr.length()) {
                                        val sObj = sentArr.getJSONObject(s)
                                        val text = sObj.optString("text", "").replace(Regex("\\+{6,}%?|\\*{4,}"), "").trim()
                                        if (text.isNotBlank() && !isMetaOrAdSentence(text)) sList.add(text)
                                    }
                                } else {
                                    val pArr = chObj.optJSONArray("paragraphs")
                                    if (pArr != null) {
                                        for (p in 0 until pArr.length()) {
                                            val pText = pArr.getString(p).replace(Regex("\\+{6,}%?|\\*{4,}"), "").trim()
                                            val split = pText.split(Regex("(?<=[.!?…])\\s+"))
                                            for (sp in split) {
                                                val trimmed = sp.trim()
                                                if (trimmed.isNotBlank() && !isMetaOrAdSentence(trimmed)) sList.add(trimmed)
                                            }
                                        }
                                    }
                                }
                                if (sList.isNotEmpty()) {
                                    return LoadedChapter(title, sList)
                                }
                            }
                        }
                    }
                } catch (_: Exception) {}
            }

            // Bundled assets fallback
            val assetName = if (novelId == "infinite-mana-in-the-apocalypse") {
                "novel_data.json"
            } else {
                "${novelId.replace('-', '_')}_data.json"
            }
            try {
                val jsonStr = appContext.assets.open(assetName).bufferedReader().use { it.readText() }
                val json = JSONObject(jsonStr)
                val chapters = json.optJSONArray("bundled_chapters") ?: json.optJSONArray("chapters")
                if (chapters != null && chIndex in 0 until chapters.length()) {
                    val chObj = chapters.getJSONObject(chIndex)
                    val title = chObj.optString("title", "Chapter ${chIndex + 1}")
                    val sList = ArrayList<String>()
                    val sentArr = chObj.optJSONArray("sentences")
                    if (sentArr != null && sentArr.length() > 0) {
                        for (s in 0 until sentArr.length()) {
                            val text = sentArr.getJSONObject(s).optString("text", "").replace(Regex("\\+{6,}%?|\\*{4,}"), "").trim()
                            if (text.isNotBlank() && !isMetaOrAdSentence(text)) sList.add(text)
                        }
                    }
                    if (sList.isNotEmpty()) return LoadedChapter(title, sList)
                }
            } catch (_: Exception) {}
        } catch (e: Exception) {
            Log.e("TTSBridge", "Error in loadChapterFromStorage: ${e.message}")
        }
        return null
    }

    @JavascriptInterface
    fun setKeepScreenOn(keepOn: Boolean) {
        activity?.runOnUiThread {
            try {
                if (keepOn) {
                    activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                } else {
                    activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                }
            } catch (e: Exception) {
                Log.e("TTSBridge", "Error setting keepScreenOn: ${e.message}")
            }
        }
    }

    @JavascriptInterface
    fun setNativeSleepTimer(minutes: Int) {
        mainHandler.post {
            sleepRunnable?.let { mainHandler.removeCallbacks(it) }
            sleepRunnable = null
            if (minutes > 0) {
                val delayMillis = minutes * 60 * 1000L
                Log.d("TTSBridge", "Setting native sleep timer for $minutes minutes ($delayMillis ms)")
                val runnable = Runnable {
                    Log.d("TTSBridge", "Native sleep timer triggered after $minutes minutes!")
                    stop()
                    webView.evaluateJavascript("window.onSleepTimerExpired && window.onSleepTimerExpired();", null)
                }
                sleepRunnable = runnable
                mainHandler.postDelayed(runnable, delayMillis)
            } else {
                Log.d("TTSBridge", "Native sleep timer cleared")
            }
        }
    }

    @JavascriptInterface
    fun speak(text: String, sentenceId: Int) {
        if (!isInitialized) return
        isPlayingActive = true
        activeSentenceIndex = sentenceId
        acquireWakeLock()
        TTSPlaybackService.start(
            appContext,
            activeNovelTitle.ifEmpty { "Infinite Reader" },
            "$activeChapterTitle • Sentence ${sentenceId + 1}/${activeSentences.size.coerceAtLeast(1)}"
        )
        val params = Bundle()
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, params, sentenceId.toString())
    }

    @JavascriptInterface
    fun stopUtterance() {
        tts?.stop()
        // Note: WakeLock and ForegroundService intentionally remain active during quick transitions
    }

    @JavascriptInterface
    fun stop() {
        isPlayingActive = false
        chapterWatchdogRunnable?.let { mainHandler.removeCallbacks(it) }
        chapterWatchdogRunnable = null
        tts?.stop()
        releaseWakeLock()
        setKeepScreenOn(false)
        TTSPlaybackService.stop(appContext)
        mainHandler.post {
            sleepRunnable?.let { mainHandler.removeCallbacks(it) }
            sleepRunnable = null
        }
    }

    fun togglePlayPause() {
        mainHandler.post {
            if (isPlayingActive) {
                stop()
                webView.evaluateJavascript("window.togglePlayFromNative && window.togglePlayFromNative(false);", null)
            } else {
                isPlayingActive = true
                acquireWakeLock()
                if (activeSentenceIndex in activeSentences.indices) {
                    speak(activeSentences[activeSentenceIndex], activeSentenceIndex)
                }
                webView.evaluateJavascript("window.togglePlayFromNative && window.togglePlayFromNative(true);", null)
            }
        }
    }

    fun nextChapter() {
        mainHandler.post {
            if (nextChapterIndex == activeChapterIndex + 1 && nextChapterSentences.isNotEmpty()) {
                advanceToNextChapterNatively()
            } else {
                webView.evaluateJavascript("window.nextChapterFromNative && window.nextChapterFromNative();", null)
            }
        }
    }

    fun prevChapter() {
        mainHandler.post {
            webView.evaluateJavascript("window.prevChapterFromNative && window.prevChapterFromNative();", null)
        }
    }

    fun syncToWebView() {
        mainHandler.post {
            webView.evaluateJavascript(
                "window.syncPlaybackState && window.syncPlaybackState($activeChapterIndex, $activeSentenceIndex, $isPlayingActive);",
                null
            )
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
            val formattedAuth = if (authHeader != null && !authHeader.startsWith("Bearer ") && !authHeader.startsWith("token ")) {
                "Bearer $authHeader"
            } else {
                authHeader
            }
            var currentUrl = urlStr
            var conn = java.net.URL(currentUrl).openConnection() as java.net.HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 20000
            conn.readTimeout = 60000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Android; Mobile)")
            conn.setRequestProperty("Accept", "application/vnd.github.raw, application/json, text/plain, */*")
            if (!formattedAuth.isNullOrEmpty() && (currentUrl.contains("github.com") || currentUrl.contains("githubusercontent.com"))) {
                conn.setRequestProperty("Authorization", formattedAuth)
            }
            conn.instanceFollowRedirects = false
            conn.connect()

            var redirectCount = 0
            while ((conn.responseCode in 301..308) && redirectCount < 5) {
                val location = conn.getHeaderField("Location") ?: break
                conn.disconnect()
                // Resolve relative and absolute redirects safely
                currentUrl = java.net.URL(java.net.URL(currentUrl), location).toString()
                conn = java.net.URL(currentUrl).openConnection() as java.net.HttpURLConnection
                conn.requestMethod = "GET"
                conn.connectTimeout = 20000
                conn.readTimeout = 60000
                conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Android; Mobile)")
                conn.setRequestProperty("Accept", "application/vnd.github.raw, application/json, text/plain, */*")
                // Only send Authorization header if target is still github.com / githubusercontent.com, NOT AWS S3!
                if (!formattedAuth.isNullOrEmpty() && (currentUrl.contains("github.com") || currentUrl.contains("githubusercontent.com"))) {
                    conn.setRequestProperty("Authorization", formattedAuth)
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
        if (activeBridgeInstance == this) {
            activeBridgeInstance = null
        }
        stop()
        tts?.shutdown()
    }
}
