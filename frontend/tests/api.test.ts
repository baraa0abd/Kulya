import { api, ApiError } from "@/lib/api";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const reply = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("API session and failure recovery", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    sessionStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());
  it("stores credentials in tab storage and clears them on logout", async () => {
    const user = { id: "u", username: "patient1", role: "patient" };
    fetchMock.mockResolvedValue(reply(200, { access: "a", refresh: "r", user }));
    expect(await api.login("patient1", " secret ")).toEqual(user);
    expect(JSON.parse(sessionStorage.getItem("kulya.session")!)).toEqual({
      access: "a",
      refresh: "r",
    });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).password).toBe(" secret ");
    api.logout();
    expect(api.hasSession()).toBe(false);
  });
  it("refreshes an expired token once and replays the request with the new token", async () => {
    sessionStorage.setItem("kulya.session", JSON.stringify({ access: "old", refresh: "r" }));
    fetchMock
      .mockResolvedValueOnce(reply(401, {}))
      .mockResolvedValueOnce(reply(200, { access: "new" }))
      .mockResolvedValueOnce(reply(200, { id: "u" }));
    expect(await api.get("/auth/me/")).toEqual({ id: "u" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2][1].headers.get("Authorization")).toBe("Bearer new");
  });
  it("clears expired sessions when refresh fails and does not loop", async () => {
    sessionStorage.setItem("kulya.session", JSON.stringify({ access: "old", refresh: "expired" }));
    fetchMock.mockResolvedValueOnce(reply(401, {})).mockResolvedValueOnce(reply(401, {}));
    await expect(api.get("/auth/me/")).rejects.toBeInstanceOf(ApiError);
    expect(api.hasSession()).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it.each([400, 403, 404, 409, 429, 500, 503])(
    "preserves structured server errors (%s)",
    async (status) => {
      fetchMock.mockResolvedValue(
        reply(status, {
          error: { code: "test_error", message: "Test failure", details: { field: ["Invalid"] } },
        }),
      );
      await expect(api.post("/test/", {})).rejects.toMatchObject({
        status,
        code: "test_error",
        message: "Test failure",
        details: { field: ["Invalid"] },
      });
    },
  );
  it("handles non-JSON server failures", async () => {
    fetchMock.mockResolvedValue(new Response("unavailable", { status: 502 }));
    await expect(api.get("/test/")).rejects.toMatchObject({
      status: 502,
      message: "Request failed.",
    });
  });
  it("accepts successful empty delete responses", async () => {
    fetchMock.mockResolvedValue(reply(204));
    await expect(api.del("/test/")).resolves.toBeUndefined();
  });
});
