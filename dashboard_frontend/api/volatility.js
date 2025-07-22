export async function calculateVolatility(payload, accessToken) {
  try {
    const response = await fetch('http://localhost:8000/api/v1_0/fyres/volatility', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      const data = await response.json();
      return { success: true, data };
    } else {
      const errorData = await response.json();
      return { success: false, error: errorData.error || 'Failed to calculate volatility' };
    }
  } catch (error) {
    return { success: false, error: 'Network error or server unavailable' };
  }
}