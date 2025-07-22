export async function runSimulation(accessToken) {
  try {
    // FIX: Corrected the API endpoint URL
    const response = await fetch('http://localhost:8000/api/v1_0/strategy/simulation', {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (response.ok) {
      const data = await response.json();
      return { success: true, data: data.data }; // Ensure we're extracting the data array
    } else {
      const errorData = await response.json().catch(() => ({ error: 'Error parsing response' }));
      return { success: false, error: errorData.error || 'Failed to run simulation' };
    }
  } catch (error) {
    console.error('Simulation error:', error);
    return { success: false, error: 'Network error or server unavailable' };
  }
}