using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Runtime.InteropServices;

namespace OpenWebUiSystray;

sealed class TrayApplicationContext : ApplicationContext
{
    private readonly NotifyIcon _trayIcon;
    private readonly string _startUrl;
    private MainForm? _mainForm;
    private GlobalHotkeyWindow? _globalHotkey;

    public TrayApplicationContext(string startUrl)
    {
        _startUrl = startUrl;

        var quitItem = new ToolStripMenuItem("Quit", null, (_, _) => Application.Exit());
        var contextMenu = new ContextMenuStrip();
        contextMenu.Items.Add(quitItem);

        _trayIcon = new NotifyIcon
        {
            Icon = GenerateIcon(),
            Text = "Open WebUI Systray",
            ContextMenuStrip = contextMenu,
            Visible = true
        };

        _trayIcon.MouseClick += OnTrayClick;

        _globalHotkey = new GlobalHotkeyWindow(ToggleMainWindow);
        if (!_globalHotkey.IsRegistered)
        {
            _globalHotkey.Dispose();
            _globalHotkey = null;
        }
    }

    private void OnTrayClick(object? sender, MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left) return;

        ToggleMainWindow();
    }

    private void ToggleMainWindow()
    {
        if (_mainForm == null || _mainForm.IsDisposed)
        {
            _mainForm = new MainForm(_startUrl) { Icon = _trayIcon.Icon };
            ShowMainWindow();
            return;
        }

        if (_mainForm.Visible && _mainForm.WindowState != FormWindowState.Minimized)
        {
            _mainForm.Hide();
            return;
        }

        ShowMainWindow();
    }

    private void ShowMainWindow()
    {
        _mainForm!.Show();
        _mainForm.WindowState = FormWindowState.Normal;
        _mainForm.BringToFront();
        _mainForm.Activate();
    }

    private static Icon GenerateIcon()
    {
        const int size = 32;
        using var bmp = new Bitmap(size, size);
        using var g = Graphics.FromImage(bmp);

        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
        g.Clear(Color.Transparent);

        var rect = new Rectangle(2, 2, size - 4, size - 4);
        using var path = RoundedRect(rect, 6);
        using (var brush = new SolidBrush(Color.White))
            g.FillPath(brush, path);

        using var font = new Font("Segoe UI", 14f, FontStyle.Bold, GraphicsUnit.Pixel);
        const string text = "OI";
        var textSize = g.MeasureString(text, font);
        float x = (size - textSize.Width) / 2f;
        float y = (size - textSize.Height) / 2f;
        using (var brush = new SolidBrush(Color.FromArgb(30, 30, 30)))
            g.DrawString(text, font, brush, x, y);

        var hIcon = bmp.GetHicon();
        using var temp = Icon.FromHandle(hIcon);
        var icon = (Icon)temp.Clone();
        DestroyIcon(hIcon);
        return icon;
    }

    [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern bool DestroyIcon(IntPtr handle);

    private static GraphicsPath RoundedRect(Rectangle bounds, int radius)
    {
        int d = radius * 2;
        var path = new GraphicsPath();
        path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
        path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
        path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
        path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _globalHotkey?.Dispose();
            _globalHotkey = null;
            _trayIcon.Visible = false;
            _trayIcon.Dispose();
            if (_mainForm is { IsDisposed: false })
                _mainForm.Close();
            _mainForm?.Dispose();
        }
        base.Dispose(disposing);
    }
}
