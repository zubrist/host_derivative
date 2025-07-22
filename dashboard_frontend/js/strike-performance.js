// Strike Performance Analysis

// Define the backend API base URL 
const API_BASE_URL = 'http://localhost:8000';

// When the page loads, check authentication status
document.addEventListener('DOMContentLoaded', function() {
  checkAuthAndRedirect();
});

// Function to check auth and redirect accordingly
function checkAuthAndRedirect() {
  const token = localStorage.getItem('authToken');
  if (!token) {
    // Not authenticated, show login form
    hideAllSections();
    document.getElementById('login-section').style.display = 'block';
  }
}

// Show the strike performance section when the button is clicked
document.getElementById('strikePerformanceApi').addEventListener('click', function() {
  // Check if token exists in localStorage
  const token = localStorage.getItem('authToken');
  console.log("Token when clicking Strike Performance button:", token ? "Token exists" : "No token found");
  
  if (token) {
    // User is authenticated, show the strike performance form
    hideAllSections();
    document.getElementById('strike-performance-section').style.display = 'block';
    
    // Set default end date to today
    const today = new Date();
    document.getElementById('sp_end_date').value = today.toISOString().split('T')[0];
  } else {
    // Not authenticated, show login form
    hideAllSections();
    document.getElementById('login-section').style.display = 'block';
    document.getElementById('loginMessage').innerHTML = 'Please log in to access this feature';
  }
});

// Handle form submission
document.getElementById('strikePerformanceForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  
  const token = localStorage.getItem('authToken');
  if (!token) {
    document.getElementById('strikePerformanceSummary').innerHTML = 
      '<div class="error-message">Authentication required</div>';
    return;
  }
  
  // Show processing state
  document.getElementById('strikePerformanceSummary').innerHTML = '<h3>Processing...</h3>';
  document.getElementById('monthlyResults').innerHTML = '';
  
  // Get form data
  const symbol = document.getElementById('sp_symbol').value;
  const endDate = document.getElementById('sp_end_date').value;
  const yearsOfData = parseInt(document.getElementById('sp_years_of_data').value);
  const customMultiplier = document.getElementById('sp_custom_multiplier').value === 'true';
  const multipliers = Array.from(document.getElementById('sp_multipliers').selectedOptions)
                    .map(option => parseFloat(option.value));
                    
  try {
    // Calculate start and end dates
    const endDateObj = new Date(endDate);
    const endYear = endDateObj.getFullYear();
    const endMonth = endDateObj.getMonth() + 1;
    
    // Run the analysis with actual API calls
    await runStrikePerformanceAnalysis({
      symbol,
      endDate,
      yearsOfData,
      customMultiplier,
      multipliers
    });
  } catch (error) {
    document.getElementById('strikePerformanceSummary').innerHTML = 
      `<div class="error-message">Error: ${error.message}</div>`;
  }
});

// The actual analysis function
async function runStrikePerformanceAnalysis(formData) {
  const { symbol, endDate, yearsOfData, customMultiplier, multipliers } = formData;
  
  // Calculate date range
  const endDateObj = new Date(endDate);
  const endYear = endDateObj.getFullYear();
  const endMonth = endDateObj.getMonth() + 1;
  
  let startYear = endYear - yearsOfData;
  let startMonth = endMonth;
  
  const monthsToAnalyze = [];
  let currentYear = startYear;
  let currentMonth = startMonth;
  
  // Generate list of months to analyze
  while (currentYear < endYear || (currentYear === endYear && currentMonth <= endMonth)) {
    monthsToAnalyze.push({ month: currentMonth, year: currentYear });
    
    currentMonth++;
    if (currentMonth > 12) {
      currentMonth = 1;
      currentYear++;
    }
  }
  
  // Performance tracking
  const overallPerformance = {
    totalPL: 0,
    wins: 0,
    losses: 0,
    profitableMonths: 0,
    unprofitableMonths: 0
  };
  
  const allResults = [];
  
  // Process each month
  for (const period of monthsToAnalyze) {
    try {
      document.getElementById('monthlyResults').innerHTML += 
        `<div id="month-${period.year}-${period.month}" class="month-result">
           <h3>Processing ${period.month}/${period.year}</h3>
        </div>`;
      
      // Get volatility data
      const volatilityData = await getVolatilityForMonth(
        period.month, 
        period.year, 
        symbol,
        customMultiplier,
        multipliers
      );
      
      // Process the data
      const monthResult = {
        month: period.month,
        year: period.year,
        pl: 0,  // Will be filled with actual data
        isProfit: false,
        details: []
      };
      
      // Get performance simulation
      const performanceData = await getMonthlyPerformanceSimulation(period.month, period.year);
      
      // Update the monthly div with real results
      const monthDiv = document.getElementById(`month-${period.year}-${period.month}`);
      monthDiv.innerHTML = createMonthResultHTML(monthResult);
      
      // Track overall performance
      allResults.push(monthResult);
      if (monthResult.isProfit) {
        overallPerformance.profitableMonths++;
      } else {
        overallPerformance.unprofitableMonths++;
      }
      overallPerformance.totalPL += monthResult.pl;
      
    } catch (error) {
      console.error(`Error processing ${period.month}/${period.year}:`, error);
      document.getElementById('monthlyResults').innerHTML += 
        `<div class="month-result error">
          <h3>Error processing ${period.month}/${period.year}</h3>
          <p>${error.message}</p>
        </div>`;
    }
  }
  
  // Display the overall summary
  displaySummary(overallPerformance, allResults);
}

// Real API call to get volatility data
async function getVolatilityForMonth(month, year, symbol, customMultiplier, multipliers) {
  const token = localStorage.getItem('authToken');
  if (!token) {
    throw new Error('Authentication required');
  }
  
  // Format month and year with leading zeros if needed
  const formattedMonth = month.toString().padStart(2, '0');
  const formattedYear = year.toString().slice(-2); // Get last two digits
  
  const response = await fetch(`${API_BASE_URL}/api/v1_0/fyres/volatility_of_month/${formattedMonth}/${formattedYear}/${encodeURIComponent(symbol)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      'request-user-id': localStorage.getItem('userId') || '1'
    }
  });
  
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('authToken');
      throw new Error('Authentication failed. Please log in again.');
    }
    
    const errorText = await response.text();
    throw new Error(`API error: ${response.status} - ${errorText}`);
  }
  
  return await response.json();
}

// Real API call for performance simulation
async function getMonthlyPerformanceSimulation(month, year) {
  const token = localStorage.getItem('authToken');
  if (!token) {
    throw new Error('Authentication required');
  }
  
  // Format month and year with leading zeros if needed
  const formattedMonth = month.toString().padStart(2, '0');
  const formattedYear = year.toString().slice(-2); // Get last two digits
  
  const response = await fetch(`${API_BASE_URL}/api/v1_0/strategy/monthly_volatility_simulation/${formattedMonth}/${formattedYear}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      'request-user-id': localStorage.getItem('userId') || '1'
    }
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Simulation API error: ${response.status} - ${errorText}`);
  }
  
  return await response.json();
}

// Helper function to display month results
function createMonthResultHTML(monthResult) {
  // You'll need to implement this based on your data structure
  return `
    <h3>${monthResult.month}/${monthResult.year}</h3>
    <p class="${monthResult.isProfit ? 'profit' : 'loss'}">
      P&L: ₹${monthResult.pl.toFixed(2)}
    </p>
    <div class="month-details">
      <!-- Add more details here -->
    </div>
  `;
}

// Helper function to display overall summary
function displaySummary(performance, results) {
  const winRate = results.length > 0 ? 
    (performance.profitableMonths / results.length * 100).toFixed(0) + '%' : 
    'N/A';
  
  document.getElementById('strikePerformanceSummary').innerHTML = `
    <div class="performance-summary">
      <div class="stat">
        <h3>Total P&L</h3>
        <p class="${performance.totalPL >= 0 ? 'profit' : 'loss'}">
          ₹${performance.totalPL.toFixed(2)}
        </p>
      </div>
      <div class="stat">
        <h3>Win Rate</h3>
        <p>${winRate}</p>
      </div>
      <div class="stat">
        <h3>Profitable Months</h3>
        <p>${performance.profitableMonths}</p>
      </div>
      <div class="stat">
        <h3>Unprofitable Months</h3>
        <p>${performance.unprofitableMonths}</p>
      </div>
    </div>
  `;
}

// Login function to ensure authentication before running any API calls
async function ensureAuthenticated() {
  const authToken = localStorage.getItem('authToken');
  
  if (!authToken) {
    throw new Error('Authentication required. Please log in first.');
  }
  
  return true;
}

async function performLogin(username, password) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      return { success: false, error: `Login failed: ${response.status} - ${errorText}` };
    }
    
    const data = await response.json();
    
    // Save auth info to localStorage
    localStorage.setItem('authToken', data.token);
    localStorage.setItem('userId', data.user_id || '1');
    
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Helper to hide all sections
function hideAllSections() {
  document.querySelectorAll('main > section').forEach(section => {
    section.style.display = 'none';
  });
}

console.log("Strike Performance JS loaded");