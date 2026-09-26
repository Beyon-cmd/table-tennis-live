using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

namespace TableTennisLive.Core.Services;

/// <summary>Compatible with the Python version's DPAPI-encrypted cloud_session.json.</summary>
public sealed class CloudSessionStore(string? dataDirectory = null)
{
    private readonly string _path = Path.Combine(CloudConfig.DataDirectory(dataDirectory),
        "cloud_session.json");

    public string? LoadRefreshToken()
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(_path));
            var encrypted = Convert.FromHexString(document.RootElement
                .GetProperty("refresh_token_dpapi").GetString() ?? "");
            return Encoding.UTF8.GetString(Protect(encrypted, decrypt: true));
        }
        catch (Exception error) when (error is IOException or JsonException or FormatException or
            KeyNotFoundException or UnauthorizedAccessException or InvalidOperationException)
        {
            return null;
        }
    }

    public void Save(CloudSession session)
    {
        var encrypted = Protect(Encoding.UTF8.GetBytes(session.RefreshToken), decrypt: false);
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        var temporary = _path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(new
        {
            user_id = session.UserId, email = session.Email,
            refresh_token_dpapi = Convert.ToHexString(encrypted).ToLowerInvariant()
        }));
        File.Move(temporary, _path, true);
    }

    public void Clear()
    {
        if (File.Exists(_path)) File.Delete(_path);
    }

    private static byte[] Protect(byte[] data, bool decrypt)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException("会话仅能在 Windows 中保存");
        var inputPointer = Marshal.AllocHGlobal(data.Length);
        try
        {
            Marshal.Copy(data, 0, inputPointer, data.Length);
            var input = new DataBlob { Length = data.Length, Data = inputPointer };
            var success = decrypt
                ? CryptUnprotectData(ref input, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero,
                    IntPtr.Zero, 1, out var output)
                : CryptProtectData(ref input, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero,
                    IntPtr.Zero, 1, out output);
            if (!success) throw new InvalidOperationException(
                $"Windows 无法加密或读取登录会话 (Win32 {Marshal.GetLastPInvokeError()})");
            try
            {
                var result = new byte[output.Length];
                Marshal.Copy(output.Data, result, 0, result.Length);
                return result;
            }
            finally { LocalFree(output.Data); }
        }
        finally { Marshal.FreeHGlobal(inputPointer); }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct DataBlob
    {
        public int Length;
        public IntPtr Data;
    }

    [DllImport("crypt32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CryptProtectData(ref DataBlob input, IntPtr description,
        IntPtr entropy, IntPtr reserved, IntPtr prompt, int flags, out DataBlob output);

    [DllImport("crypt32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CryptUnprotectData(ref DataBlob input, IntPtr description,
        IntPtr entropy, IntPtr reserved, IntPtr prompt, int flags, out DataBlob output);

    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr memory);
}
