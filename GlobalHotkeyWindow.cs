using System.Runtime.InteropServices;

namespace OpenWebUiSystray;

/// <summary>
/// Message-only window that registers a global hotkey (Ctrl+Alt+O). Dispose to unregister.
/// </summary>
sealed class GlobalHotkeyWindow : NativeWindow, IDisposable
{
    private const uint ModAlt = 0x0001;
    private const uint ModControl = 0x0002;
    private const int HotkeyId = 1;
    private const uint Modifiers = ModControl | ModAlt;
    private const uint VkO = 0x4F;

    private const int WmHotkey = 0x0312;

    private readonly Action _onHotkey;
    private bool _registered;

    public GlobalHotkeyWindow(Action onHotkey)
    {
        _onHotkey = onHotkey;
        var cp = new CreateParams
        {
            Parent = new IntPtr(-3), // HWND_MESSAGE
        };
        CreateHandle(cp);
        if (!RegisterHotKey(Handle, HotkeyId, Modifiers, VkO))
        {
            DestroyHandle();
            return;
        }

        _registered = true;
    }

    public bool IsRegistered => _registered;

    protected override void WndProc(ref Message m)
    {
        if (m.Msg == WmHotkey && m.WParam.ToInt32() == HotkeyId)
        {
            _onHotkey();
            return;
        }

        base.WndProc(ref m);
    }

    public void Dispose()
    {
        if (_registered && Handle != IntPtr.Zero)
        {
            UnregisterHotKey(Handle, HotkeyId);
            _registered = false;
        }

        if (Handle != IntPtr.Zero)
            DestroyHandle();
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);
}
