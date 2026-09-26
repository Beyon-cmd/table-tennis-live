using System.Text;
using System.Text.Json;

namespace TableTennisLive.Core.Services;

public sealed record CloudConfig(Uri ProjectUrl, string PublishableKey)
{
    public static CloudConfig Create(string address, string key)
    {
        if (!Uri.TryCreate(address.Trim(), UriKind.Absolute, out var supplied) ||
            supplied.Scheme != Uri.UriSchemeHttps || supplied.UserInfo.Length > 0 ||
            supplied.Query.Length > 0 || supplied.Fragment.Length > 0 ||
            supplied.AbsolutePath is not ("/" or "/rest/v1/" or "/rest/v1"))
            throw new ArgumentException("请输入 Supabase 项目 HTTPS 地址（可带 /rest/v1/）");
        var normalized = key.Trim().Replace("\\_", "_");
        if (normalized.Length == 0 || normalized.StartsWith("sb_secret_", StringComparison.Ordinal))
            throw new ArgumentException("只可使用 publishable / anon key，不可使用管理员密钥");
        if (normalized.Count(c => c == '.') == 2)
        {
            try
            {
                var part = normalized.Split('.')[1].Replace('-', '+').Replace('_', '/');
                var json = Encoding.UTF8.GetString(Convert.FromBase64String(part.PadRight(
                    (part.Length + 3) / 4 * 4, '=')));
                using var document = JsonDocument.Parse(json);
                var role = document.RootElement.GetProperty("role").GetString();
                var project = document.RootElement.GetProperty("ref").GetString();
                if (role != "anon" || project != supplied.Host.Split('.')[0])
                    throw new ArgumentException("anon key 与项目地址不匹配");
            }
            catch (Exception error) when (error is FormatException or JsonException or KeyNotFoundException)
            {
                throw new ArgumentException("anon key 格式无效", error);
            }
        }
        return new(new Uri(supplied.GetLeftPart(UriPartial.Authority) + "/"), normalized);
    }

    public static CloudConfig? Load(string? dataDirectory = null)
    {
        var url = Environment.GetEnvironmentVariable("TABLE_TENNIS_SUPABASE_URL");
        var key = Environment.GetEnvironmentVariable("TABLE_TENNIS_SUPABASE_KEY");
        if (!string.IsNullOrWhiteSpace(url) && !string.IsNullOrWhiteSpace(key))
            return Create(url, key);
        var path = Path.Combine(DataDirectory(dataDirectory), "cloud_config.json");
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            return Create(document.RootElement.GetProperty("url").GetString() ?? "",
                document.RootElement.GetProperty("publishable_key").GetString() ?? "");
        }
        catch (Exception error) when (error is IOException or JsonException or
            UnauthorizedAccessException or ArgumentException or KeyNotFoundException)
        {
            return null;
        }
    }

    public void Save(string? dataDirectory = null)
    {
        var directory = DataDirectory(dataDirectory);
        Directory.CreateDirectory(directory);
        var path = Path.Combine(directory, "cloud_config.json");
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(new
        {
            url = ProjectUrl.ToString().TrimEnd('/'), publishable_key = PublishableKey
        }));
        File.Move(temporary, path, true);
    }

    internal static string DataDirectory(string? overrideDirectory) => overrideDirectory ??
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "TableTennisLive");
}
