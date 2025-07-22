export async function login(username, password) {
  try {
    const response = await fetch('http://localhost:8000/api/v1_0/user_login', { // Use absolute URL
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });

    if (response.ok) {
      const data = await response.json();
      return { success: true, accessToken: data.access_token };
    } else {
      const errorData = await response.json();
      return { success: false, error: errorData.detail || 'Login failed' };
    }
  } catch (error) {
    return { success: false, error: 'Network error or server unavailable' };
  }
}