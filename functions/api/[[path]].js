const ORIGIN = "http://124.221.146.23:8080";

export async function onRequest(context) {
  const incomingUrl = new URL(context.request.url);

  // 调试接口：确认 Function 是否真的部署成功
  if (incomingUrl.pathname === "/api/__debug") {
    return Response.json({
      ok: true,
      message: "Pages Function is running",
      origin: ORIGIN,
      path: incomingUrl.pathname,
      time: new Date().toISOString(),
    });
  }

  try {
    const targetUrl = new URL(
      incomingUrl.pathname + incomingUrl.search,
      ORIGIN
    );

    const headers = new Headers(context.request.headers);

    // 这些头不要转发给你的 Go 后端
    headers.delete("host");
    headers.delete("cf-connecting-ip");
    headers.delete("cf-ipcountry");
    headers.delete("cf-ray");
    headers.delete("cf-visitor");
    headers.delete("x-forwarded-proto");
    headers.delete("x-real-ip");

    const init = {
      method: context.request.method,
      headers,
      redirect: "manual",
    };

    if (
      context.request.method !== "GET" &&
      context.request.method !== "HEAD"
    ) {
      init.body = context.request.body;
    }

    const resp = await fetch(targetUrl.toString(), init);

    // 原样返回后端响应
    return new Response(resp.body, {
      status: resp.status,
      statusText: resp.statusText,
      headers: resp.headers,
    });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error: String(err?.stack || err),
      },
      {
        status: 500,
      }
    );
  }
}