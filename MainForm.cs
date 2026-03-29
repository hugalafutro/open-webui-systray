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

    private readonly WebView2 _webView;
    private readonly string _startUrl;
    private int _navRetries;
    private PendingNavKind _pendingNavKind;
    private bool _retryDueWhenVisible;
    private bool _webViewInitialized;
    private DateTime? _lastHiddenUtc;

    private const int MaxNavRetries = 30;
    private const int RetryDelayMs = 5_000;
    private const int ShowRefreshAfterHideMinutes = 10;

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
            _webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
            _webView.CoreWebView2.Settings.IsZoomControlEnabled = false;
            _webView.ZoomFactor = 0.9;

            var startUri = new Uri(_startUrl);
            var allowedHost = startUri.Host;
            _webView.CoreWebView2.NavigationStarting += (_, args) =>
            {
                if (!IsNavigationAllowed(args.Uri, allowedHost))
                    args.Cancel = true;
            };

            _webView.CoreWebView2.NavigationCompleted += OnNavigationCompleted;

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
            _navRetries = 0;
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
