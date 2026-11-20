package com.giveaway.viewer

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.SharedPreferences
import android.content.res.ColorStateList
import android.os.Bundle
import android.os.Process
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private val base = "http://127.0.0.1:8000"

    private lateinit var serverDot: View
    private lateinit var serverStateBadge: TextView
    private lateinit var btnToggleServer: Button
    private lateinit var apiGroup: View
    private lateinit var inputApiId: EditText
    private lateinit var inputApiHash: EditText
    private lateinit var inputPhone: EditText
    private lateinit var inputOtp: EditText
    private lateinit var inputPassword: EditText
    private lateinit var btnSendCode: Button
    private lateinit var btnVerify: Button
    private lateinit var otpGroup: View
    private lateinit var loginPanel: View
    private lateinit var statusText: TextView
    private lateinit var consoleLog: TextView
    private lateinit var webView: WebView
    private lateinit var prefs: SharedPreferences

    @Volatile
    private var serverRunning = false
    private val logLines = ArrayDeque<String>()
    private val timeFmt = SimpleDateFormat("HH:mm:ss", Locale.US)
    private val executor = Executors.newCachedThreadPool()

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        serverDot = findViewById(R.id.serverDot)
        serverStateBadge = findViewById(R.id.serverStateBadge)
        btnToggleServer = findViewById(R.id.btnToggleServer)
        apiGroup = findViewById(R.id.apiGroup)
        inputApiId = findViewById(R.id.inputApiId)
        inputApiHash = findViewById(R.id.inputApiHash)
        inputPhone = findViewById(R.id.inputPhone)
        inputOtp = findViewById(R.id.inputOtp)
        inputPassword = findViewById(R.id.inputPassword)
        btnSendCode = findViewById(R.id.btnSendCode)
        btnVerify = findViewById(R.id.btnVerify)
        otpGroup = findViewById(R.id.otpGroup)
        loginPanel = findViewById(R.id.loginPanel)
        statusText = findViewById(R.id.statusText)
        consoleLog = findViewById(R.id.consoleLog)
        webView = findViewById(R.id.webView)

        prefs = getSharedPreferences("giveaway_prefs", MODE_PRIVATE)
        val savedPhone = prefs.getString("phone", "")?.takeIf { it.isNotBlank() } ?: "+959953237832"
        inputPhone.setText(savedPhone)
        val savedId = prefs.getString("api_id", null)?.takeIf { it.isNotBlank() }
        val savedHash = prefs.getString("api_hash", null)?.takeIf { it.isNotBlank() }
        val apiId = savedId ?: BuildConfig.TG_API_ID
        val apiHash = savedHash ?: BuildConfig.TG_API_HASH
        inputApiId.setText(apiId)
        inputApiHash.setText(apiHash)
        if (apiId.isBlank() || apiHash.isBlank()) apiGroup.visibility = View.VISIBLE

        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.addJavascriptInterface(object {
            @JavascriptInterface
            fun copyToClipboard(text: String) {
                val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                cm.setPrimaryClip(ClipData.newPlainText("Giveaway Comments", text))
            }
        }, "AndroidBridge")
        webView.webViewClient = WebViewClient()
        webView.webChromeClient = WebChromeClient()

        btnToggleServer.setOnClickListener {
            if (serverRunning) stopServer() else startServerThen { checkStatus() }
        }
        btnSendCode.setOnClickListener { sendCode() }
        btnVerify.setOnClickListener { verify() }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.visibility == View.VISIBLE && webView.canGoBack()) webView.goBack()
                else finish()
            }
        })

        updateServerUi(false)
        appendLog("init chaquopy runtime (py3.12 · telethon 1.43.2)")

        if (apiGroup.visibility == View.VISIBLE) {
            btnSendCode.text = "Start server & send code"
            setStatus("[WARN] Enter TG_API_ID / TG_API_HASH and phone number")
        } else {
            startServerThen { checkStatus() }
        }
    }

    private fun appendLog(msg: String) {
        runOnUiThread {
            val ts = timeFmt.format(Date())
            if (logLines.size >= 14) logLines.removeFirst()
            logLines.addLast("[$ts] $msg")
            consoleLog.text = logLines.joinToString("\n")
        }
    }

    private fun updateServerUi(running: Boolean, starting: Boolean = false) {
        serverRunning = running
        val pid = Process.myPid()
        when {
            starting -> {
                serverDot.setBackgroundColor(getColor(R.color.warning_amber))
                serverStateBadge.text = "STARTING · pid $pid"
                serverStateBadge.setTextColor(getColor(R.color.warning_amber))
                btnToggleServer.text = "WAIT..."
                btnToggleServer.isEnabled = false
                btnToggleServer.backgroundTintList = ColorStateList.valueOf(getColor(R.color.border_dark))
            }
            running -> {
                serverDot.setBackgroundColor(getColor(R.color.success_green))
                serverStateBadge.text = "RUNNING · pid $pid · 127.0.0.1:8000"
                serverStateBadge.setTextColor(getColor(R.color.success_green))
                btnToggleServer.text = "■ STOP"
                btnToggleServer.isEnabled = true
                btnToggleServer.backgroundTintList = ColorStateList.valueOf(getColor(R.color.error_red))
            }
            else -> {
                serverDot.setBackgroundColor(getColor(R.color.error_red))
                serverStateBadge.text = "STOPPED · offline"
                serverStateBadge.setTextColor(getColor(R.color.text_muted))
                btnToggleServer.text = "▶ RUN"
                btnToggleServer.isEnabled = true
                btnToggleServer.backgroundTintList = ColorStateList.valueOf(getColor(R.color.success_green))
            }
        }
    }

    private fun setStatus(msg: String, error: Boolean = false) {
        statusText.text = msg
        statusText.setTextColor(getColor(if (error) R.color.error_red else R.color.text_muted))
        appendLog(msg)
    }

    private fun stopServer() {
        appendLog("sending SIGTERM to uvicorn server...")
        btnToggleServer.isEnabled = false
        executor.execute {
            try {
                if (Python.isStarted()) {
                    Python.getInstance().getModule("android_bridge").callAttr("stop_server")
                }
            } catch (_: Exception) {}
            runOnUiThread {
                updateServerUi(false)
                webView.loadUrl("about:blank")
                webView.visibility = View.GONE
                loginPanel.visibility = View.VISIBLE
                setStatus("[STOPPED] Daemon halted. Tap ▶ RUN to restart.")
            }
        }
    }

    /** Starts the embedded Python server, waits until it answers, then runs [next]. */
    private fun startServerThen(next: () -> Unit) {
        val apiId = inputApiId.text.toString().trim()
        val apiHash = inputApiHash.text.toString().trim()
        if (apiId.isEmpty() || apiHash.isEmpty()) {
            apiGroup.visibility = View.VISIBLE
            setStatus("[ERR] TG_API_ID and TG_API_HASH required", true)
            return
        }
        if (apiId.toIntOrNull() == null) {
            apiGroup.visibility = View.VISIBLE
            setStatus("[ERR] TG_API_ID must be numeric", true)
            return
        }
        prefs.edit().putString("api_id", apiId).putString("api_hash", apiHash).apply()
        updateServerUi(running = false, starting = true)
        setStatus("[BOOT] Starting FastAPI/Uvicorn on 127.0.0.1:8000...")
        btnSendCode.isEnabled = false
        executor.execute {
            var error: String? = null
            try {
                if (!Python.isStarted()) Python.start(AndroidPlatform(applicationContext))
                val res = Python.getInstance().getModule("android_bridge")
                    .callAttr("start_server", apiId, apiHash, filesDir.absolutePath, 8000)
                    .toString()
                appendLog("android_bridge.start_server() -> $res")
                var ready = false
                repeat(40) {
                    if (!ready) {
                        try {
                            val c = URL("$base/health").openConnection() as HttpURLConnection
                            c.connectTimeout = 500
                            ready = c.responseCode == 200
                        } catch (_: Exception) {
                            Thread.sleep(500)
                        }
                    }
                }
                if (!ready) error = "Health check timeout (127.0.0.1:8000/health)"
            } catch (e: Exception) {
                error = e.message ?: e.javaClass.simpleName
            }
            runOnUiThread {
                btnSendCode.isEnabled = true
                if (error != null) {
                    updateServerUi(false)
                    apiGroup.visibility = View.VISIBLE
                    setStatus("[ERR] Server boot failed: $error", true)
                } else {
                    updateServerUi(true)
                    appendLog("GET /health -> 200 OK")
                    next()
                }
            }
        }
    }

    private fun request(
        method: String,
        path: String,
        body: JSONObject? = null,
        done: (Int, JSONObject?, String?) -> Unit
    ) {
        appendLog("$method $path")
        executor.execute {
            var code = -1
            var json: JSONObject? = null
            var err: String? = null
            try {
                val conn = URL(base + path).openConnection() as HttpURLConnection
                conn.requestMethod = method
                conn.connectTimeout = 8000
                conn.readTimeout = 60000
                if (body != null) {
                    conn.doOutput = true
                    conn.setRequestProperty("Content-Type", "application/json")
                    conn.outputStream.use { it.write(body.toString().toByteArray()) }
                }
                code = conn.responseCode
                val stream = if (code < 400) conn.inputStream else conn.errorStream
                val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
                json = try { JSONObject(text) } catch (_: Exception) { null }
            } catch (e: Exception) {
                err = e.message ?: e.javaClass.simpleName
            }
            runOnUiThread {
                appendLog("$method $path -> HTTP $code")
                done(code, json, err)
            }
        }
    }

    private fun checkStatus() {
        request("GET", "/auth/status") { code, json, err ->
            if (code == 200 && json?.optBoolean("authorized") == true) {
                val user = json.optString("name", "user")
                appendLog("session authorized as '$user'")
                openWeb()
            } else if (code == 200) {
                setStatus("[AUTH] Session unauthorized. Send OTP to sign in.")
            } else {
                setStatus(err ?: json?.optString("error") ?: "HTTP $code", true)
            }
        }
    }

    private fun sendCode() {
        val rawPhone = inputPhone.text.toString().trim()
        if (rawPhone.isEmpty()) {
            setStatus("[ERR] Phone number is required", true)
            return
        }
        val digits = rawPhone.filter { it.isDigit() }
        val phone = when {
            digits.length == 10 && digits.startsWith("9595") -> "+95995" + digits.substring(4)
            digits.startsWith("09") -> "+959" + digits.substring(2)
            digits.isNotEmpty() -> "+$digits"
            else -> rawPhone
        }
        if (phone != rawPhone) inputPhone.setText(phone)
        prefs.edit().putString("phone", phone).apply()
        startServerThen {
            btnSendCode.isEnabled = false
            setStatus("[MTProto] Requesting OTP for $phone...")
            request("POST", "/auth/send_code", JSONObject().put("phone", phone)) { code, json, err ->
                btnSendCode.isEnabled = true
                btnSendCode.text = "POST /auth/send_code (Resend)"
                if (code == 200) {
                    otpGroup.visibility = View.VISIBLE
                    inputPassword.visibility = View.GONE
                    inputPassword.setText("")
                    setStatus("[OK] OTP dispatched via Telegram. Enter code below.")
                } else {
                    apiGroup.visibility = View.VISIBLE
                    setStatus(err ?: json?.optString("error") ?: "HTTP $code", true)
                }
            }
        }
    }

    private fun verify() {
        val otp = inputOtp.text.toString().trim()
        val pw = inputPassword.text.toString()
        val needPassword = inputPassword.visibility == View.VISIBLE
        if (needPassword && pw.isEmpty()) {
            setStatus("[ERR] 2FA password required", true)
            return
        }
        if (!needPassword && otp.isEmpty()) {
            setStatus("[ERR] OTP code required", true)
            return
        }
        val body = JSONObject().put("code", if (needPassword) "" else otp)
        if (pw.isNotEmpty()) body.put("password", pw)
        btnVerify.isEnabled = false
        setStatus("[MTProto] Verifying credentials...")
        request("POST", "/auth/verify", body) { code, json, err ->
            btnVerify.isEnabled = true
            when {
                code == 200 && json?.optBoolean("authorized") == true -> openWeb()
                code == 200 && json?.optBoolean("password_required") == true -> {
                    inputPassword.visibility = View.VISIBLE
                    inputPassword.requestFocus()
                    setStatus("[2FA] SessionPasswordNeededError: enter 2FA password")
                }
                else -> setStatus(err ?: json?.optString("error") ?: "HTTP $code", true)
            }
        }
    }

    private fun openWeb() {
        loginPanel.visibility = View.GONE
        webView.visibility = View.VISIBLE
        webView.loadUrl(base)
    }

    override fun onDestroy() {
        super.onDestroy()
        executor.execute {
            try {
                if (Python.isStarted())
                    Python.getInstance().getModule("android_bridge").callAttr("stop_server")
            } catch (_: Exception) {}
        }
        executor.shutdown()
    }
}
