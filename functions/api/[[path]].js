const ORIGIN = "http://124-221-146-23.sslip.io:8080";

export async function onRequest(context) {
  const incomingUrl = new URL(context.request.url);

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
    headers.delete("host");

    const init = {
      method: context.request.method,
      headers,
      redirect: "manual",
    };

    if (context.request.method !== "GET" && context.request.method !== "HEAD") {
      init.body = context.request.body;
    }

    const resp = await fetch(targetUrl.toString(), init);

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