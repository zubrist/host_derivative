console.log("app.js loaded");

// Configuration
const CONFIG = {
  API_BASE_URL: 'http://localhost:8000',
  TOKEN_KEY: 'access_token',
  USER_ID_KEY: 'user_id'
};

// API Service - Consolidated API calls
const ApiService = {
  // Generic API call method
  async call(endpoint, options = {}) {
    const token = localStorage.getItem(CONFIG.TOKEN_KEY);
    const defaultOptions = {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      }
    };

    const finalOptions = { ...defaultOptions, ...options };
    if (finalOptions.body && typeof finalOptions.body === 'object') {
      finalOptions.body = JSON.stringify(finalOptions.body);
    }

    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, finalOptions);
      const data = await response.json();
      
      if (response.ok) {
        return { success: true, data };
      } else {
        return { success: false, error: data.detail || 'API Error', status: response.status };
      }
    } catch (error) {
      return { success: false, error: 'Network error', status: 0 };
    }
  },

  // Authentication
  async login(username, password) {
    return this.call('/api/v1_0/user_login', {
      method: 'POST',
      body: { username, password }
    });
  },

  // Volatility API
  async getVolatility(payload) {
    return this.call('/api/v1_0/fyres/volatility', {
      method: 'POST',
      body: payload
    });
  },

  async getMonthlyVolatility(mm, yy, symbol) {
    return this.call(`/api/v1_0/fyres/volatility_of_month/${mm}/${yy}/${encodeURIComponent(symbol)}`);
  },

  // Simulation API
  async runSimulation(symbol) {
    return this.call(`/api/v1_0/strategy/simulation?symbol=${encodeURIComponent(symbol)}`);
  },

  async getMonthlySimulation(mm, yy) {
    return this.call(`/api/v1_0/strategy/monthly_volatility_simulation/${mm}/${yy}`);
  },

  // Transactions API
  async getTransactions(symbol) {
    return this.call(`/api/v1_0/transactions?symbol=${encodeURIComponent(symbol)}`);
  },

  async getActiveTransactions() {
    const userId = localStorage.getItem(CONFIG.USER_ID_KEY);
    return this.call('/api/v1_0/get_active_transactions', {
      headers: { 'request-user-id': userId }
    });
  },

  async createTransaction(payload) {
    const userId = localStorage.getItem(CONFIG.USER_ID_KEY);
    return this.call('/api/v1_0/create_transection', {
      method: 'POST',
      body: payload,
      headers: { 'request-user-id': userId }
    });
  },

  async deleteTransaction(transactionId) {
    const userId = localStorage.getItem(CONFIG.USER_ID_KEY);
    return this.call(`/api/v1_0/delete_transaction/${transactionId}`, {
      method: 'DELETE',
      headers: { 'request-user-id': userId }
    });
  }
};

// Authentication Manager
const AuthManager = {
  isAuthenticated() {
    return !!localStorage.getItem(CONFIG.TOKEN_KEY);
  },

  login(accessToken, userData = {}) {
    localStorage.setItem(CONFIG.TOKEN_KEY, accessToken);
    if (userData.user_id) {
      localStorage.setItem(CONFIG.USER_ID_KEY, userData.user_id);
    }
  },

  logout() {
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    localStorage.removeItem(CONFIG.USER_ID_KEY);
    UIManager.showSection('login-section');
  },

  getToken() {
    return localStorage.getItem(CONFIG.TOKEN_KEY);
  },

  getUserId() {
    return localStorage.getItem(CONFIG.USER_ID_KEY);
  }
};

// UI Manager - Handles all UI operations
const UIManager = {
  showSection(id) {
    document.querySelectorAll('section').forEach(s => s.style.display = 'none');
    const section = document.getElementById(id);
    if (section) {
      section.style.display = 'block';
    }
  },

  showMessage(elementId, message, isError = false) {
    const element = document.getElementById(elementId);
    if (element) {
      element.textContent = message;
      element.className = isError ? 'error' : '';
    }
  },

  clearForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
      form.reset();
    }
  },

  displayResult(elementId, data, isError = false) {
    const element = document.getElementById(elementId);
    if (element) {
      if (isError) {
        element.innerHTML = `<span class="error">${data}</span>`;
      } else {
        element.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
      }
    }
  }
};

// Application Main Controller
const App = {
  init() {
    this.setupEventListeners();
    this.checkAuthentication();
  },

  checkAuthentication() {
    if (AuthManager.isAuthenticated()) {
      UIManager.showSection('dashboard-section');
    } else {
      UIManager.showSection('login-section');
    }
  },

  setupEventListeners() {
    // Login form
    document.getElementById('loginForm').addEventListener('submit', this.handleLogin.bind(this));
    
    // Logout button
    document.getElementById('logoutButton').addEventListener('click', this.handleLogout.bind(this));
    
    // API buttons
    document.querySelectorAll('.api-btn').forEach(btn => {
      btn.addEventListener('click', this.handleApiButton.bind(this));
    });
    
    // Back to dashboard
    document.getElementById('backToDashboard').addEventListener('click', this.handleBackToDashboard.bind(this));
  },

  async handleLogin(e) {
    e.preventDefault();
    console.log("Login form submitted");
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    UIManager.showMessage('loginMessage', 'Logging in...');
    
    const result = await ApiService.login(username, password);
    
    if (result.success && result.data.access_token) {
      AuthManager.login(result.data.access_token, result.data.data);
      UIManager.showMessage('loginMessage', '');
      UIManager.showSection('dashboard-section');
      UIManager.clearForm('loginForm');
    } else {
      UIManager.showMessage('loginMessage', result.error || 'Login failed', true);
    }
  },

  handleLogout() {
    AuthManager.logout();
  },

  handleApiButton(e) {
    const api = e.target.getAttribute('data-api');
    this.loadApiForm(api);
  },

  handleBackToDashboard() {
    UIManager.showSection('dashboard-section');
    document.getElementById('api-form-container').innerHTML = '';
    document.getElementById('api-result').innerHTML = '';
  },

  loadApiForm(api) {
    UIManager.showSection('api-form-section');
    const container = document.getElementById('api-form-container');
    container.innerHTML = ''; // Clear previous

    if (api === 'volatility') {
      this.loadVolatilityForm(container);
    } else if (api === 'simulation') {
      this.loadSimulationForm(container);
    } else if (api === 'transactions') {
      this.loadTransactionsForm(container);
    } else if (api === 'strike-performance') {
      this.loadStrikePerformanceForm(container);
    }
  },

  loadVolatilityForm(container) {
    container.innerHTML = `
      <h3>Volatility API</h3>
      <form id="volForm">
        <input type="text" id="symbol" placeholder="Symbol" required>
        <input type="date" id="end_date" required>
        <input type="number" id="years_of_data" placeholder="Years of Data" required>
        <button type="submit">Submit</button>
      </form>
    `;
    
    document.getElementById('volForm').onsubmit = async (e) => {
      e.preventDefault();
      const payload = {
        symbol: document.getElementById('symbol').value,
        end_date: document.getElementById('end_date').value,
        years_of_data: document.getElementById('years_of_data').value
      };
      await this.callGenericApi('getVolatility', payload);
    };
  },

  loadSimulationForm(container) {
    container.innerHTML = `
      <h3>Simulation API</h3>
      <form id="simForm">
        <input type="text" id="sim_symbol" placeholder="Symbol" required>
        <button type="submit">Run Simulation</button>
      </form>
    `;
    
    document.getElementById('simForm').onsubmit = async (e) => {
      e.preventDefault();
      const symbol = document.getElementById('sim_symbol').value;
      await this.callGenericApi('runSimulation', symbol);
    };
  },

  loadTransactionsForm(container) {
    container.innerHTML = `
      <h3>Transactions API</h3>
      <div class="form-group">
        <button id="getActiveTransBtn" type="button">Get Active Transactions</button>
        <button id="createTransBtn" type="button">Create Transaction</button>
      </div>
      <div id="transactionForms"></div>
    `;
    
    document.getElementById('getActiveTransBtn').onclick = async () => {
      await this.callGenericApi('getActiveTransactions');
    };
    
    document.getElementById('createTransBtn').onclick = () => {
      this.showCreateTransactionForm();
    };
  },

  showCreateTransactionForm() {
    const formsDiv = document.getElementById('transactionForms');
    formsDiv.innerHTML = `
      <h4>Create New Transaction</h4>
      <form id="createTransForm">
        <input type="text" id="trans_symbol" placeholder="Symbol (e.g., NIFTY)" required>
        <input type="text" id="trans_instrument" placeholder="Instrument (e.g., OPTIDX)" required>
        <input type="number" id="trans_strike" placeholder="Strike Price" required>
        <select id="trans_option_type" required>
          <option value="">Select Option Type</option>
          <option value="CE">Call (CE)</option>
          <option value="PE">Put (PE)</option>
        </select>
        <input type="number" id="trans_lots" placeholder="Number of Lots" required>
        <input type="date" id="trans_trade_date" required>
        <input type="date" id="trans_expiry_date" required>
        <button type="submit">Create Transaction</button>
      </form>
    `;
    
    // Set default dates
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('trans_trade_date').value = today;
    
    document.getElementById('createTransForm').onsubmit = async (e) => {
      e.preventDefault();
      const payload = {
        symbol: document.getElementById('trans_symbol').value,
        instrument: document.getElementById('trans_instrument').value,
        strike_price: parseFloat(document.getElementById('trans_strike').value),
        option_type: document.getElementById('trans_option_type').value,
        lots: parseInt(document.getElementById('trans_lots').value),
        trade_date: document.getElementById('trans_trade_date').value,
        expiry_date: document.getElementById('trans_expiry_date').value
      };
      await this.callGenericApi('createTransaction', payload);
    };
  },

  loadStrikePerformanceForm(container) {
    container.innerHTML = `
      <h3>Strike Performance API</h3>
      <form id="strikeForm">
        <div class="form-group">
          <label for="sp_symbol">Symbol:</label>
          <input type="text" id="sp_symbol" value="NSE:NIFTY50-INDEX" required>
        </div>
        
        <div class="form-group">
          <label for="sp_end_date">End Date:</label>
          <input type="date" id="sp_end_date" required>
        </div>
        
        <div class="form-group">
          <label for="sp_years_of_data">Number of Months:</label>
          <input type="number" id="sp_years_of_data" value="12" min="1" max="24" required>
        </div>
        
        <div class="form-group">
          <button type="submit">Analyze</button>
        </div>
      </form>
      
      <div id="api-result"></div>
    `;
    
    // Set default date to today
    document.getElementById('sp_end_date').valueAsDate = new Date();
    
    document.getElementById('strikeForm').onsubmit = async (e) => {
      e.preventDefault();
      await this.handleStrikePerformanceAnalysis();
    };
  },

  async callGenericApi(method, ...args) {
    const resultDiv = document.getElementById('api-result');
    resultDiv.textContent = 'Loading...';
    
    const result = await ApiService[method](...args);
    
    if (result.success) {
      UIManager.displayResult('api-result', result.data);
    } else {
      UIManager.displayResult('api-result', result.error, true);
    }
  },

  async handleStrikePerformanceAnalysis() {
    const resultDiv = document.getElementById('api-result');
    resultDiv.innerHTML = ''; // Clear previous results

    const symbol = document.getElementById('sp_symbol').value;
    const endDateStr = document.getElementById('sp_end_date').value;
    const numMonths = parseInt(document.getElementById('sp_years_of_data').value, 10);

    // Calculate months to analyze
    const months = [];
    const startDate = new Date(endDateStr);
    startDate.setUTCDate(1);
    startDate.setUTCMonth(startDate.getUTCMonth() - 1);

    for (let i = 0; i < numMonths; i++) {
      months.push({
        mm: String(startDate.getUTCMonth() + 1).padStart(2, '0'),
        year: startDate.getUTCFullYear()
      });
      startDate.setUTCMonth(startDate.getUTCMonth() - 1);
    }
    months.reverse();

    // Fetch and display each month sequentially
    for (const m of months) {
      const mm = m.mm;
      const yy = String(m.year).slice(-2);
      
      // Show loading for this month
      const loadingId = `loading-${mm}-${m.year}`;
      resultDiv.innerHTML += `<div id="${loadingId}">Loading ${mm}/${m.year}...</div>`;

      try {
        // Call both APIs
        const [volResult, simResult] = await Promise.all([
          ApiService.getMonthlyVolatility(mm, yy, symbol),
          ApiService.getMonthlySimulation(mm, yy)
        ]);

        if (volResult.success) {
          // Create the complete HTML with both volatility data and PnL table
          const monthHtml = this.createMonthSection(mm, m.year, volResult.data, simResult.data);
          
          // Replace the loading div
          const loadingDiv = document.getElementById(loadingId);
          loadingDiv.outerHTML = monthHtml;
        } else {
          // Handle volatility API error
          const loadingDiv = document.getElementById(loadingId);
          loadingDiv.outerHTML = `<div class="date-header">${mm}/${m.year}</div><span class="error">${volResult.error || 'API Error'}</span>`;
        }
      } catch (err) {
        // Handle network error
        const loadingDiv = document.getElementById(loadingId);
        if(loadingDiv) loadingDiv.outerHTML = `<div class="date-header">${mm}/${m.year}</div><span class="error">Network error</span>`;
      }
    }
  },

  createMonthSection(mm, year, volData, simData) {
    const hasSimData = simData && simData.status === "success";
    
    // Build the complete strike card with integrated PnL table
    const symbol = volData.symbol || '';
    const targetMonth = volData.target_month || '';
    const spot = volData.volatility_metrics?.spot ?? '';
    const metrics = volData.volatility_metrics || {};
    const strikes = volData.strikes || {};
    const vbs = strikes.volatility_based_strikes?.["range_1.5sd"] || {};
    const sbs = strikes.spot_based_strikes || {};

    const pnlSection = hasSimData ? this.createPnlTable(simData.data) : `
      <div class="strike-card-section">
        <div class="section-title">PnL Data</div>
        <div style="padding: 20px; text-align: center;">
          <span class="error">PnL data not available</span>
        </div>
      </div>
    `;

    return `
      <div class="date-header">${mm}/${year}</div>
      <div class="strike-card">
        <div class="strike-card-header">
          <span>Symbol: <b>${symbol}</b></span>
          <span>Target Month: <b>${targetMonth}</b></span>
          <span>Spot: <b>${spot}</b></span>
        </div>
        <div class="strike-card-body">
          <div class="strike-card-section metrics">
            <div class="section-title">Volatility Metrics</div>
            <div class="metric-row"><span>mean</span><span>${metrics.mean !== undefined ? metrics.mean.toFixed(4) : '-'}</span></div>
            <div class="metric-row"><span>variance</span><span>${metrics.variance !== undefined ? metrics.variance.toFixed(4) : '-'}</span></div>
            <div class="metric-row"><span>daily_volatility</span><span>${metrics.daily_volatility !== undefined ? metrics.daily_volatility.toFixed(4) : '-'}</span></div>
            <div class="metric-row"><span>monthly_volatility</span><span>${metrics.monthly_volatility !== undefined ? metrics.monthly_volatility.toFixed(4) : '-'}</span></div>
          </div>
          <div class="strike-card-section strikes">
            <div class="section-title">Strikes</div>
            <div class="strike-row">
              <div class="strike-label">Volatility Range 1.5sd</div>
              <div>Lower SELL PE: <b>${vbs.lower_strike ?? '-'}</b>, Upper BUY CE: <b>${vbs.upper_strike ?? '-'}</b></div>
            </div>
            <div class="strike-row">
              <div class="strike-label">Spot Based</div>
              <div>Lower SELL PE: <b>${sbs.lower_strike ?? '-'}</b>, Upper BUY CE: <b>${sbs.upper_strike ?? '-'}</b></div>
            </div>
          </div>
        </div>
        ${pnlSection}
      </div>
    `;
  },

  createPnlTable(apiData) {
    if (!apiData || !apiData.daily_pnl) {
      return `<div class="strike-card-section">
        <div class="section-title">📊 PnL Summary</div>
        <div style="padding: 20px; text-align: center;">
          <span class="error">No PnL data available</span>
        </div>
      </div>`;
    }

    const dailyPnl = apiData.daily_pnl;
    const positions = apiData.positions;
    const totalRealizedPnl = apiData.total_realized_pnl || 0;

    // Debug logging
    console.log('API Data:', apiData);
    console.log('Daily PnL:', dailyPnl);
    console.log('Positions:', positions);

    // Get the last day's data for final PnL
    const lastDay = dailyPnl[dailyPnl.length - 1];

    // Create compact position summary in single row
    const positionSummaryRows = positions.map((pos, index) => {
      const finalPnl = lastDay ? (lastDay.unrealised[index]?.pnl || 0) : 0;
      const entryPrice = pos.entry_price || 0;
      const lots = pos.lots || 0;
      
      const statusIcon = finalPnl > 0 ? '🚀' : finalPnl < 0 ? '📉' : '⚡';
      
      return `
        <div class="position-summary-row">
          <div class="position-info">
            <div class="position-strike">
              <span style="font-size: 14px;">${statusIcon}</span>
              <strong>${pos.strike} ${pos.option_type}</strong>
            </div>
            <div class="position-price-qty">
              <span class="entry-price">₹${entryPrice.toLocaleString()}</span>
              <span class="position-details">Qty: ${lots}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Create the detailed table
    const expandId = `detailed-table-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    const tableHeaders = positions.map(pos => 
      `<th>${pos.strike} ${pos.option_type}</th>`
    ).join('');

    const tableRows = dailyPnl.map((day, dayIndex) => {
      const dateObj = new Date(day.date);
      const formattedDate = `${String(dateObj.getDate()).padStart(2, '0')}-${String(dateObj.getMonth() + 1).padStart(2, '0')}`;
      
      const positionCells = positions.map((pos, index) => {
        const pnl = day.unrealised[index]?.pnl || 0;
        const pnlClass = pnl > 0 ? 'profit' : pnl < 0 ? 'loss' : 'neutral';
        return `<td class="pnl-${pnlClass}">₹${pnl.toLocaleString()}</td>`;
      }).join('');

      // Calculate total daily P&L
      const dailyTotal = positions.reduce((total, pos, index) => {
        const pnl = day.unrealised[index]?.pnl || 0;
        return total + pnl;
      }, 0);
      
      // Debug logging for each row
      console.log(`Day ${formattedDate}: Daily total = ${dailyTotal}`, day.unrealised);
      
      const dailyTotalClass = dailyTotal > 0 ? 'profit' : dailyTotal < 0 ? 'loss' : 'neutral';
      const dailyTotalFormatted = dailyTotal === 0 ? '₹0' : `₹${dailyTotal.toLocaleString()}`;

      return `
        <tr>
          <td class="date-cell">${formattedDate}</td>
          ${positionCells}
          <td class="pnl-${dailyTotalClass} total-pnl"><strong>${dailyTotalFormatted}</strong></td>
        </tr>
      `;
    }).join('');

    return `
      <div class="strike-card-section">
        <div class="section-title">📊 PnL Summary</div>
        
        <div class="pnl-overview-new">
          <div class="pnl-metric-new">
            <span class="pnl-label-new">💰 Total Realized PnL</span>
            <span class="pnl-value-new ${totalRealizedPnl >= 0 ? 'profit' : 'loss'}">₹${totalRealizedPnl.toLocaleString()}</span>
          </div>
          <div class="pnl-metric-new">
            <span class="pnl-label-new">🎯 Strategy</span>
            <span class="pnl-value-new">${apiData.strategy_type || 'Monthly Volatility'}</span>
          </div>
          <div class="pnl-metric-new">
            <span class="pnl-label-new">📅 Days</span>
            <span class="pnl-value-new">${dailyPnl.length}</span>
          </div>
        </div>

        <div class="detailed-pnl-container">
          <div class="position-summary-section">
            <h4>📋 Position Summary</h4>
            <div class="position-summary-list">
              ${positionSummaryRows}
            </div>
          </div>

          <div class="expand-button-container">
            <button class="expand-details-btn" onclick="toggleDetailedTable('${expandId}')">
              <span id="btn-text-${expandId}">📊 Expand Details</span>
              <span class="expand-icon" id="icon-${expandId}">▼</span>
            </button>
          </div>

          <div class="detailed-table-container" id="${expandId}" style="display: none;">
            <div class="table-scroll-container">
              <table class="detailed-pnl-table">
                <thead>
                  <tr>
                    <th class="date-header">📅 Date</th>
                    ${tableHeaders}
                    <th class="total-header">💰 Total P/L</th>
                  </tr>
                </thead>
                <tbody>
                  ${tableRows}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    `;
  }
};

// Global function for expanding/collapsing PnL details
function toggleDetailedTable(tableId) {
  const table = document.getElementById(tableId);
  const btnText = document.getElementById(`btn-text-${tableId}`);
  const icon = document.getElementById(`icon-${tableId}`);
  
  if (table.style.display === 'none') {
    table.style.display = 'block';
    btnText.textContent = '📊 Collapse Daily Details';
    icon.textContent = '▲';
    icon.style.transform = 'rotate(180deg)';
  } else {
    table.style.display = 'none';
    btnText.textContent = '📊 Expand Daily Details';
    icon.textContent = '▼';
    icon.style.transform = 'rotate(0deg)';
  }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
