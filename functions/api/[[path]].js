const ORIGIN = "http://124.221.146.23:8080";

export async function onRequest(context) {
  const incomingUrl = new URL(context.request.url);

  const targetUrl = new URL(
    incomingUrl.pathname + incomingUrl.search,
    ORIGIN
  );

  return fetch(new Request(targetUrl, context.request));
}