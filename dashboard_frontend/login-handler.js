// Remove any import statements that are causing errors
console.log("Loading login-handler.js");

// Real API base URL
const API_BASE_URL = 'http://localhost:8000';

// Global variable to store token
let accessToken = '';

// Login form handler - added directly without waiting for DOMContentLoaded
document.getElementById('loginForm').addEventListener('submit', function(e) {
  e.preventDefault();
  console.log("Login form submitted");
  
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  
  console.log("Login attempt with:", username);
  
  // Simple test login
  localStorage.setItem('authToken', 'test_token_123');
  localStorage.setItem('userId', '1');
  
  console.log("Auth token set:", localStorage.getItem('authToken'));
  
  document.getElementById('loginMessage').innerHTML = 'Login successful!';
  
  // Show API section
  hideAllSections();
  document.getElementById('api-section').style.display = 'block';
});

// Check if we're already logged in
const savedToken = localStorage.getItem('accessToken');
if (savedToken) {
  accessToken = savedToken;
  document.getElementById('login-section').style.display = 'none';
  document.getElementById('api-section').style.display = 'block';
}

// Set up other API buttons here
document.getElementById('volatilityApi').addEventListener('click', function() {
  // Volatility API logic
  document.getElementById('volatility-section').style.display = 'block';
});

document.getElementById('simulationApi').addEventListener('click', function() {
  // Simulation API logic
});

// Logout button handler
document.getElementById('logoutButton').addEventListener('click', function() {
  console.log("Logout clicked");
  
  localStorage.removeItem('authToken');
  localStorage.removeItem('userId');
  
  hideAllSections();
  document.getElementById('login-section').style.display = 'block';
  document.getElementById('loginMessage').innerHTML = 'You have been logged out';
});