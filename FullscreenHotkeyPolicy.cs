using System.Runtime.InteropServices;

namespace OpenWebUiSystray;

/// <summary>
/// Decides when the tray app should unregister its global hotkey so the foreground app can receive Ctrl+Alt+O.
/// Exclusive fullscreen (some games) may not report a normal window rect; borderless and video fullscreen on primary are the main targets.
/// </summary>
static class FullscreenHotkeyPolicy
{
    private const uint MonitorDefaultNull = 0;
    private const uint MonitorDefaultPrimary = 1;

    private const int TolerancePx = 8;

    /// <summary>
    /// When true, the app should call <see cref="GlobalHotkeyWindow.Unregister"/> so the chord is not owned globally.
    /// </summary>
    /// <param name="mainFormHandle">Handle of this app's main window, if it exists; foreground match never yields.</param>
    public static bool ShouldYieldGlobalHotkey(Func<IntPtr?> mainFormHandle)
    {
        var fg = GetForegroundWindow();
        if (fg == IntPtr.Zero)
            return false;

        var ours = mainFormHandle();
        if (ours.HasValue && fg == ours.Value)
            return false;

        if (IsIconic(fg))
            return false;

        var hMonitor = MonitorFromWindow(fg, MonitorDefaultNull);
        if (hMonitor == IntPtr.Zero)
            return false;

        var primary = MonitorFromPoint(default, MonitorDefaultPrimary);
        if (hMonitor != primary)
            return false;

        if (!GetWindowRect(fg, out var wr))
            return false;

        var mi = new MonitorInfo
        {
            cbSize = Marshal.SizeOf<MonitorInfo>()
        };
        if (!GetMonitorInfo(hMonitor, ref mi))
            return false;

        return CoversRect(wr, mi.rcWork, TolerancePx) || CoversRect(wr, mi.rcMonitor, TolerancePx);
    }

    private static bool CoversRect(RECT window, RECT target, int tol)
    {
        return window.Left <= target.Left + tol
            && window.Top <= target.Top + tol
            && window.Right >= target.Right - tol
            && window.Bottom >= target.Bottom - tol;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MonitorInfo
    {
        public int cbSize;
        public RECT rcMonitor;
        public RECT rcWork;
        public uint dwFlags;
    }

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    private static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern IntPtr MonitorFromWindow(IntPtr hwnd, uint dwFlags);

    [DllImport("user32.dll")]
    private static extern IntPtr MonitorFromPoint(POINT pt, uint dwFlags);

    [DllImport("user32.dll")]
    private static extern bool GetMonitorInfo(IntPtr hMonitor, ref MonitorInfo lpmi);

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT
    {
        public int X;
        public int Y;
    }
}
