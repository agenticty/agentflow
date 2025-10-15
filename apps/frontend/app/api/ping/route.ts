export async function GET() {
    const res = await fetch("http://localhost:8000/api/health", { cache: "no-store" });
    const data = await res.json();
    return new Response(JSON.stringify(data), { headers: { "content-type": "application/json" } });
  }
  