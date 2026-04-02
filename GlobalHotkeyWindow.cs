using System.Runtime.InteropServices;

namespace OpenWebUiSystray;

/// <summary>
/// Message-only window that registers a global hotkey (Ctrl+Alt+O). Call <see cref="TryRegister"/> after construction;
/// use <see cref="Unregister"/> to release the chord without destroying the window. Dispose to tear down.
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
    }

    /// <summary>Returns true if the global hotkey is currently registered with the system.</summary>
    public bool IsRegistered => _registered;

    /// <summary>Registers Ctrl+Alt+O if not already registered. Returns false if another app owns the chord.</summary>
    public bool TryRegister()
    {
        if (_registered)
            return true;
        if (Handle == IntPtr.Zero)
            return false;
        if (!RegisterHotKey(Handle, HotkeyId, Modifiers, VkO))
            return false;
        _registered = true;
        return true;
    }

    /// <summary>Unregisters the hotkey but keeps the message-only window (allows <see cref="TryRegister"/> later).</summary>
    public void Unregister()
    {
        if (!_registered || Handle == IntPtr.Zero)
            return;
        UnregisterHotKey(Handle, HotkeyId);
        _registered = false;
    }

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
