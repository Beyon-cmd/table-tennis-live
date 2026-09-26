using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace TableTennisLive.Core.Services;

public sealed record CloudSession(string UserId, string Email, string AccessToken,
    string RefreshToken, DateTimeOffset ExpiresAt);

/// <summary>Supabase Auth and owner-scoped PostgREST; only public keys belong in this client.</summary>
public sealed class CloudApi(CloudConfig config) : IDisposable
{
    private readonly HttpClient _http = new() { BaseAddress = config.ProjectUrl,
        Timeout = TimeSpan.FromSeconds(15) };

    public async Task<CloudSession> SignInAsync(string email, string password, CancellationToken ct)
    {
        using var response = await SendAsync(HttpMethod.Post,
            "auth/v1/token?grant_type=password", null,
            new { email = email.Trim(), password }, null, ct);
        using var payload = await ReadAsync(response, ct);
        return Session(payload.RootElement);
    }

    public async Task<CloudSession?> SignUpAsync(string email, string password, CancellationToken ct)
    {
        using var response = await SendAsync(HttpMethod.Post, "auth/v1/signup", null,
            new { email = email.Trim(), password }, null, ct);
        using var payload = await ReadAsync(response, ct);
        return payload.RootElement.TryGetProperty("access_token", out _) ?
            Session(payload.RootElement) : null;
    }

    public async Task<CloudSession> RefreshAsync(string refreshToken, CancellationToken ct)
    {
        using var response = await SendAsync(HttpMethod.Post,
            "auth/v1/token?grant_type=refresh_token", null,
            new { refresh_token = refreshToken }, null, ct);
        using var payload = await ReadAsync(response, ct);
        return Session(payload.RootElement);
    }

    public async Task<HashSet<string>> FavoritesAsync(CloudSession session, CancellationToken ct)
    {
        HashSet<string> result = [];
        for (var offset = 0; ; offset += 1000)
        {
            var path = "rest/v1/user_favorites?select=match_id&user_id=" +
                Uri.EscapeDataString("eq." + session.UserId);
            using var request = Request(HttpMethod.Get, path, session.AccessToken);
            request.Headers.Range = new RangeHeaderValue(offset, offset + 999);
            using var response = await _http.SendAsync(request, ct);
            using var payload = await ReadAsync(response, ct);
            if (payload.RootElement.ValueKind != JsonValueKind.Array)
                throw new InvalidDataException("云端关注列表格式异常");
            var count = 0;
            foreach (var item in payload.RootElement.EnumerateArray())
            {
                count++;
                if (item.TryGetProperty("match_id", out var id) && id.ValueKind == JsonValueKind.String)
                    result.Add(id.GetString()!);
            }
            if (count < 1000) return result;
        }
    }

    public async Task PushAsync(CloudSession session,
        IReadOnlyDictionary<string, bool> changes, CancellationToken ct)
    {
        var additions = changes.Where(row => row.Value).Select(row => new
        { user_id = session.UserId, match_id = row.Key }).ToArray();
        if (additions.Length > 0)
        {
            using var response = await SendAsync(HttpMethod.Post,
                "rest/v1/user_favorites?on_conflict=user_id,match_id", session.AccessToken,
                additions, "resolution=merge-duplicates,return=minimal", ct);
            await EnsureSuccessAsync(response, ct);
        }
        foreach (var (id, enabled) in changes)
        {
            if (enabled) continue;
            var path = "rest/v1/user_favorites?user_id=" +
                Uri.EscapeDataString("eq." + session.UserId) + "&match_id=" +
                Uri.EscapeDataString("eq." + id);
            using var response = await SendAsync(HttpMethod.Delete, path,
                session.AccessToken, null, "return=minimal", ct);
            await EnsureSuccessAsync(response, ct);
        }
    }

    private HttpRequestMessage Request(HttpMethod method, string path, string? token)
    {
        var request = new HttpRequestMessage(method, path);
        request.Headers.TryAddWithoutValidation("apikey", config.PublishableKey);
        if (token is not null)
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        return request;
    }

    private async Task<HttpResponseMessage> SendAsync(HttpMethod method, string path,
        string? token, object? body, string? prefer, CancellationToken ct)
    {
        using var request = Request(method, path, token);
        if (body is not null) request.Content = JsonContent.Create(body, body.GetType());
        if (prefer is not null) request.Headers.TryAddWithoutValidation("Prefer", prefer);
        return await _http.SendAsync(request, ct);
    }

    private static async Task<JsonDocument> ReadAsync(HttpResponseMessage response,
        CancellationToken ct)
    {
        await EnsureSuccessAsync(response, ct);
        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        return await JsonDocument.ParseAsync(stream, cancellationToken: ct);
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage response,
        CancellationToken ct)
    {
        if (response.IsSuccessStatusCode) return;
        var detail = "";
        try
        {
            using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
            foreach (var field in new[] { "msg", "message", "error_description", "error" })
                if (body.RootElement.TryGetProperty(field, out var value) &&
                    value.ValueKind == JsonValueKind.String)
                { detail = value.GetString() ?? ""; break; }
        }
        catch (JsonException) { }
        throw new HttpRequestException(detail.Length > 0 ? detail :
            $"云端请求失败 ({(int)response.StatusCode})", null, response.StatusCode);
    }

    private static CloudSession Session(JsonElement data)
    {
        var user = data.GetProperty("user");
        var id = user.GetProperty("id").GetString();
        var access = data.GetProperty("access_token").GetString();
        var refresh = data.GetProperty("refresh_token").GetString();
        if (!Guid.TryParse(id, out _) || string.IsNullOrEmpty(access) ||
            string.IsNullOrEmpty(refresh))
            throw new InvalidDataException("尚未建立登录会话，请确认邮箱后登录");
        var email = user.TryGetProperty("email", out var value) ? value.GetString() ?? "" : "";
        var seconds = data.TryGetProperty("expires_in", out var expires) &&
            expires.TryGetInt32(out var parsed) ? parsed : 3600;
        return new(id!, email, access, refresh,
            DateTimeOffset.UtcNow.AddSeconds(Math.Max(60, seconds)));
    }

    public void Dispose() => _http.Dispose();
}
