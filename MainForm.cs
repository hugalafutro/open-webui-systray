using System.Diagnostics;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace OpenWebUiSystray;

sealed class MainForm : Form
{
    private enum PendingNavKind
    {
        Unknown,
        Main,
        BlankClear,
    }

    private WebView2 _webView;
    private readonly string _startUrl;
    private string _allowedHost = "";
    private int _navRetries;
    private PendingNavKind _pendingNavKind;
    private bool _retryDueWhenVisible;
    private bool _webViewInitialized;
    private DateTime? _lastHiddenUtc;
    private CoreWebView2DevToolsProtocolEventReceiver? _networkLoadingFailedReceiver;
    private bool _forceFreshProfileOnNextTlsRecovery;

    private int _certRecoveryCount;
    private bool _certRecoveryInProgress;
    private DateTime _lastTlsRecoveryStartUtc;
    private readonly object _certRecoveryLock = new();

    private const int MaxNavRetries = 30;
    private const int RetryDelayMs = 5_000;
    private const int ShowRefreshAfterHideMinutes = 10;
    private const int MaxCertRecoveries = 2;
    private static readonly TimeSpan TlsRecoveryDebounce = TimeSpan.FromSeconds(3);

    public MainForm(string startUrl)
    {
        _startUrl = startUrl;
        Text = "Open WebUI Systray";
        Size = new System.Drawing.Size(1280, 800);
        StartPosition = FormStartPosition.Manual;
        var wa = (Screen.PrimaryScreen ?? Screen.AllScreens[0]).WorkingArea;
        Location = new System.Drawing.Point(wa.Right - Width, wa.Bottom - Height);
        BackColor = Color.Black;

        _webView = new WebView2
        {
            Dock = DockStyle.Fill,
            DefaultBackgroundColor = Color.Black,
        };
        Controls.Add(_webView);
    }

    protected override async void OnLoad(EventArgs e)
    {
        base.OnLoad(e);

        try
        {
            var dataDir = Path.Combine(AppContext.BaseDirectory, "WebView2Data");
            var env = await CoreWebView2Environment.CreateAsync(
                userDataFolder: dataDir);

            await _webView.EnsureCoreWebView2Async(env);
            await WireWebViewAsync();

            _webViewInitialized = true;
            NavigateMain();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                this,
                $"Could not start the embedded browser (WebView2).\n\n{ex.Message}",
                Text,
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            Application.Exit();
        }
    }

    private async Task WireWebViewAsync()
    {
        _allowedHost = new Uri(_startUrl).Host;
        _webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
        _webView.CoreWebView2.Settings.IsZoomControlEnabled = false;
        _webView.ZoomFactor = 0.9;

        _webView.CoreWebView2.NavigationStarting += OnNavigationStarting;
        _webView.CoreWebView2.NavigationCompleted += OnNavigationCompleted;
        _webView.CoreWebView2.ServerCertificateErrorDetected += OnServerCertificateErrorDetected;
        _webView.CoreWebView2.NewWindowRequested += OnNewWindowRequested;

        _networkLoadingFailedReceiver = _webView.CoreWebView2.GetDevToolsProtocolEventReceiver("Network.loadingFailed");
        _networkLoadingFailedReceiver.DevToolsProtocolEventReceived += OnDevToolsNetworkLoadingFailed;
        await _webView.CoreWebView2.CallDevToolsProtocolMethodAsync("Network.enable", "{}");
    }

    private void UnwireWebView()
    {
        if (_webView.CoreWebView2 == null)
            return;

        _webView.CoreWebView2.NavigationStarting -= OnNavigationStarting;
        _webView.CoreWebView2.NavigationCompleted -= OnNavigationCompleted;
        _webView.CoreWebView2.ServerCertificateErrorDetected -= OnServerCertificateErrorDetected;
        _webView.CoreWebView2.NewWindowRequested -= OnNewWindowRequested;
        if (_networkLoadingFailedReceiver != null)
        {
            _networkLoadingFailedReceiver.DevToolsProtocolEventReceived -= OnDevToolsNetworkLoadingFailed;
            _networkLoadingFailedReceiver = null;
        }
    }

    private void OnDevToolsNetworkLoadingFailed(object? sender, CoreWebView2DevToolsProtocolEventReceivedEventArgs e)
    {
        try
        {
            using var doc = JsonDocument.Parse(e.ParameterObjectAsJson);
            if (!doc.RootElement.TryGetProperty("errorText", out var errorTextNode))
                return;

            var errorText = errorTextNode.GetString();
            if (!string.Equals(errorText, "net::ERR_CERT_VERIFIER_CHANGED", StringComparison.Ordinal))
                return;

            _forceFreshProfileOnNextTlsRecovery = true;
            BeginInvoke(EnqueueTlsRecovery);
        }
        catch
        {
            // Ignore malformed DevTools payloads.
        }
    }

    private void OnNavigationStarting(object? sender, CoreWebView2NavigationStartingEventArgs args)
    {
        if (IsNavigationAllowed(args.Uri, _allowedHost))
            return;

        if (IsExternalHttpUrl(args.Uri, _allowedHost))
            TryOpenInDefaultBrowser(args.Uri);

        args.Cancel = true;
    }

    private void OnNewWindowRequested(object? sender, CoreWebView2NewWindowRequestedEventArgs e)
    {
        if (string.IsNullOrEmpty(e.Uri) || !IsExternalHttpUrl(e.Uri, _allowedHost))
            return;

        e.Handled = true;
        TryOpenInDefaultBrowser(e.Uri);
    }

    private static bool IsExternalHttpUrl(string uriString, string allowedHost)
    {
        if (string.IsNullOrEmpty(uriString))
            return false;

        if (!Uri.TryCreate(uriString, UriKind.Absolute, out var uri))
            return false;

        if (!string.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase) &&
            !string.Equals(uri.Scheme, Uri.UriSchemeHttp, StringComparison.OrdinalIgnoreCase))
            return false;

        return !string.Equals(uri.Host, allowedHost, StringComparison.OrdinalIgnoreCase);
    }

    private static void TryOpenInDefaultBrowser(string uriString)
    {
        try
        {
            Process.Start(new ProcessStartInfo(uriString) { UseShellExecute = true });
        }
        catch
        {
            // Shell may reject malformed or blocked URIs; ignore.
        }
    }

    private void OnServerCertificateErrorDetected(object? sender, CoreWebView2ServerCertificateErrorDetectedEventArgs e)
    {
        e.Action = CoreWebView2ServerCertificateErrorAction.Cancel;
        BeginInvoke(EnqueueTlsRecovery);
    }

    private void EnqueueTlsRecovery()
    {
        _ = TryRecoverWebViewFromTlsAsync();
    }

    private async Task TryRecoverWebViewFromTlsAsync()
    {
        await Task.Yield();

        lock (_certRecoveryLock)
        {
            if (_certRecoveryInProgress || _certRecoveryCount >= MaxCertRecoveries)
                return;
            var now = DateTime.UtcNow;
            if (now - _lastTlsRecoveryStartUtc < TlsRecoveryDebounce)
                return;
            _lastTlsRecoveryStartUtc = now;
            _certRecoveryInProgress = true;
            _certRecoveryCount++;
        }

        try
        {
            var dataDir = Path.Combine(AppContext.BaseDirectory, "WebView2Data");
            var profileDir = _forceFreshProfileOnNextTlsRecovery
                ? Path.Combine(AppContext.BaseDirectory, "WebView2Data-recovery")
                : dataDir;

            UnwireWebView();
            Controls.Remove(_webView);
            _webView.Dispose();

            _webView = new WebView2
            {
                Dock = DockStyle.Fill,
                DefaultBackgroundColor = Color.Black,
            };
            Controls.Add(_webView);

            var env = await CoreWebView2Environment.CreateAsync(userDataFolder: profileDir);
            await _webView.EnsureCoreWebView2Async(env);
            await WireWebViewAsync();

            _pendingNavKind = PendingNavKind.Unknown;
            NavigateMain();
        }
        finally
        {
            lock (_certRecoveryLock)
                _certRecoveryInProgress = false;
        }
    }

    protected override void OnVisibleChanged(EventArgs e)
    {
        base.OnVisibleChanged(e);

        if (!Visible)
        {
            if (_webViewInitialized)
                _lastHiddenUtc = DateTime.UtcNow;
            return;
        }

        if (!_webViewInitialized || _webView.CoreWebView2 == null)
            return;

        if (_retryDueWhenVisible)
        {
            _retryDueWhenVisible = false;
            _lastHiddenUtc = null;
            NavigateMain();
            return;
        }

        if (_lastHiddenUtc.HasValue)
        {
            var hiddenFor = DateTime.UtcNow - _lastHiddenUtc.Value;
            _lastHiddenUtc = null;
            if (hiddenFor >= TimeSpan.FromMinutes(ShowRefreshAfterHideMinutes))
                _webView.CoreWebView2.Reload();
        }
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (e.CloseReason == CloseReason.UserClosing)
        {
            e.Cancel = true;
            Hide();
            return;
        }
        base.OnFormClosing(e);
    }

    private void NavigateMain()
    {
        _pendingNavKind = PendingNavKind.Main;
        _webView.CoreWebView2.Navigate(_startUrl);
    }

    private void NavigateBlankClear()
    {
        _pendingNavKind = PendingNavKind.BlankClear;
        _webView.CoreWebView2.NavigateToString("");
    }

    private async void OnNavigationCompleted(object? sender, CoreWebView2NavigationCompletedEventArgs args)
    {
        var kind = _pendingNavKind;
        _pendingNavKind = PendingNavKind.Unknown;

        if (kind == PendingNavKind.BlankClear)
            return;

        if (kind != PendingNavKind.Main)
            return;

        if (!args.IsSuccess && IsCertificateWebError(args.WebErrorStatus))
        {
            BeginInvoke(EnqueueTlsRecovery);
            return;
        }

        bool shouldRetry = !args.IsSuccess || args.HttpStatusCode >= 500;
        if (shouldRetry && _navRetries < MaxNavRetries)
        {
            if (!Visible)
            {
                _retryDueWhenVisible = true;
                return;
            }

            _navRetries++;
            NavigateBlankClear();
            await Task.Delay(RetryDelayMs);
            NavigateMain();
            return;
        }

        if (args.IsSuccess && args.HttpStatusCode < 400)
        {
            _navRetries = 0;
            _certRecoveryCount = 0;
            _forceFreshProfileOnNextTlsRecovery = false;
        }
    }

    private static bool IsCertificateWebError(CoreWebView2WebErrorStatus status)
    {
        return status is CoreWebView2WebErrorStatus.CertificateCommonNameIsIncorrect
            or CoreWebView2WebErrorStatus.CertificateExpired
            or CoreWebView2WebErrorStatus.ClientCertificateContainsErrors
            or CoreWebView2WebErrorStatus.CertificateRevoked
            or CoreWebView2WebErrorStatus.CertificateIsInvalid;
    }

    private static bool IsNavigationAllowed(string uriString, string allowedHost)
    {
        if (string.IsNullOrEmpty(uriString))
            return true;

        if (uriString.StartsWith("#", StringComparison.Ordinal))
            return true;

        if (!Uri.TryCreate(uriString, UriKind.Absolute, out var uri))
            return false;

        if (string.Equals(uri.Scheme, "about", StringComparison.OrdinalIgnoreCase))
            return true;

        if (string.Equals(uri.Scheme, "data", StringComparison.OrdinalIgnoreCase))
            return true;

        if (string.Equals(uri.Scheme, "blob", StringComparison.OrdinalIgnoreCase))
            return true;

        if (string.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase) ||
            string.Equals(uri.Scheme, Uri.UriSchemeHttp, StringComparison.OrdinalIgnoreCase))
            return string.Equals(uri.Host, allowedHost, StringComparison.OrdinalIgnoreCase);

        return false;
    }
}
