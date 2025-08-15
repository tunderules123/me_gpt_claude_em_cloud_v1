const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export async function getHistory() {
  const response = await fetch(`${BACKEND_URL}/api/history`, {
    method: "GET",
  });
  
  if (!response.ok) {
    throw new Error(`GET /history failed: ${response.status}`);
  }
  
  return response.json();
}

export async function sendMessage(content, tags, timeoutMs = 60000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  
  try {
    const response = await fetch(`${BACKEND_URL}/api/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content, tags }),
      signal: controller.signal,
    });
    
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`POST /send failed: ${response.status} ${text}`);
    }
    
    return response.json();
  } finally {
    clearTimeout(timeout);
  }
}

export async function resetChat() {
  const response = await fetch(`${BACKEND_URL}/api/reset`, {
    method: "POST",
  });
  
  if (!response.ok) {
    throw new Error(`POST /reset failed: ${response.status}`);
  }
  
  return response.json();
}