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
    const userId = localStorage.getItem(CONFIG.USER_ID_KEY);
    
    const defaultHeaders = {
      'Content-Type': 'application/json'
    };
    
    // Add Authorization header if token exists
    if (token) {
      defaultHeaders['Authorization'] = `Bearer ${token}`;
    }
    
    const defaultOptions = {
      method: 'GET',
      headers: defaultHeaders
    };

    const finalOptions = { ...defaultOptions, ...options };
    
    // Merge headers properly
    if (options.headers) {
      finalOptions.headers = { ...defaultHeaders, ...options.headers };
    }
    
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
    console.log('Getting active transactions for user:', userId);
    
    if (!userId) {
      console.error('No user ID found in localStorage');
      return { success: false, error: 'User ID not found' };
    }
    
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
  },

  async deleteAllTransactions() {
    const userId = localStorage.getItem(CONFIG.USER_ID_KEY);
    console.log('Deleting all transactions for user:', userId);
    
    if (!userId) {
      console.error('No user ID found in localStorage');
      return { success: false, error: 'User ID not found' };
    }
    
    return this.call('/api/v1_0/delete_user_transactions', {
      method: 'DELETE',
      headers: { 'request-user-id': userId }
    });
  },

  // Custom Strategy Analysis API
  async analyzeCustomStrategy(payload) {
    return this.call('/api/v1_0/analyze_custom_strategy', {
      method: 'POST',
      body: payload
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
      // Load transactions when already authenticated
      this.loadTransactions();
    } else {
      UIManager.showSection('login-section');
    }
  },

  setupEventListeners() {
    // Login form
    document.getElementById('loginForm').addEventListener('submit', this.handleLogin.bind(this));
    
    // Logout button
    document.getElementById('logoutButton').addEventListener('click', this.handleLogout.bind(this));
    
    // Refresh transactions button
    document.getElementById('refreshTransactions').addEventListener('click', this.loadTransactions.bind(this));
    
    // Delete all transactions button
    document.getElementById('deleteAllTransactions').addEventListener('click', this.deleteAllTransactions.bind(this));
    
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
    console.log('Login result:', result);
    
    if (result.success && result.data.access_token) {
      console.log('Login successful, user data:', result.data.data);
      AuthManager.login(result.data.access_token, result.data.data);
      UIManager.showMessage('loginMessage', '');
      UIManager.showSection('dashboard-section');
      UIManager.clearForm('loginForm');
      
      // Automatically load transactions after successful login
      await this.loadTransactions();
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
    } else if (api === 'monthly-volatility') {
      this.loadMonthlyVolatilityForm(container);
    } else if (api === 'simulation') {
      this.loadSimulationForm(container);
    } else if (api === 'transactions') {
      this.loadTransactionsForm(container);
    } else if (api === 'strike-performance') {
      this.loadStrikePerformanceForm(container);
    } else if (api === 'custom-strategy') {
      this.loadCustomStrategyForm(container);
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

  loadMonthlyVolatilityForm(container) {
    container.innerHTML = `
      <h3>Monthly Volatility API</h3>
      <form id="monthlyVolForm">
        <div class="form-group">
          <label for="monthly_symbol">Symbol</label>
          <input type="text" id="monthly_symbol" placeholder="NSE:NIFTY50-INDEX" value="NSE:NIFTY50-INDEX" required>
        </div>
        <div class="form-group">
          <label for="month">Month (MM)</label>
          <input type="text" id="month" placeholder="01" pattern="[0-9]{2}" maxlength="2" required>
        </div>
        <div class="form-group">
          <label for="year">Year (YY)</label>
          <input type="text" id="year" placeholder="24" pattern="[0-9]{2}" maxlength="2" required>
        </div>
        <div class="form-group">
          <button type="submit">Calculate Monthly Volatility</button>
        </div>
      </form>
    `;
    
    document.getElementById('monthlyVolForm').onsubmit = async (e) => {
      e.preventDefault();
      const month = document.getElementById('month').value;
      const year = document.getElementById('year').value;
      const symbol = document.getElementById('monthly_symbol').value;
      
      // Validate inputs
      if (!/^\d{2}$/.test(month) || parseInt(month) < 1 || parseInt(month) > 12) {
        UIManager.displayResult('api-result', 'Month must be a 2-digit number between 01 and 12', true);
        return;
      }
      
      if (!/^\d{2}$/.test(year)) {
        UIManager.displayResult('api-result', 'Year must be a 2-digit number (e.g., 24 for 2024)', true);
        return;
      }
      
      await App.callMonthlyVolatilityApi(month, year, symbol);
    };
  },

  async callMonthlyVolatilityApi(month, year, symbol) {
    try {
      UIManager.displayResult('api-result', 'Calculating monthly volatility...');
      
      const result = await ApiService.getMonthlyVolatility(month, year, symbol);
      
      if (result.success) {
        UIManager.displayResult('api-result', result.data);
      } else {
        UIManager.displayResult('api-result', result.error, true);
      }
    } catch (error) {
      console.error('Monthly volatility API error:', error);
      UIManager.displayResult('api-result', 'Failed to call monthly volatility API', true);
    }
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
              <div>Lower SELL PE: <b>${vbs.lower_strike ?? '-'}</b>, Upper SELL CE: <b>${vbs.upper_strike ?? '-'}</b></div>
            </div>
            <div class="strike-row">
              <div class="strike-label">Spot Based</div>
              <div>Lower BUY PE: <b>${sbs.lower_strike ?? '-'}</b>, Upper BUY CE: <b>${sbs.upper_strike ?? '-'}</b></div>
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

    // Calculate daily totals and find max PnL
    const dailyTotals = dailyPnl.map((day, dayIndex) => {
      const dateObj = new Date(day.date);
      const formattedDate = `${String(dateObj.getDate()).padStart(2, '0')}-${String(dateObj.getMonth() + 1).padStart(2, '0')}`;
      
      const dailyTotal = positions.reduce((total, pos, index) => {
        const pnl = day.unrealised[index]?.pnl || 0;
        return total + pnl;
      }, 0);
      
      return {
        date: formattedDate,
        total: dailyTotal,
        dayIndex
      };
    });

    // Find max PnL and its date
    const maxPnlEntry = dailyTotals.reduce((max, current) => 
      current.total > max.total ? current : max
    );
    const maxPnl = maxPnlEntry.total;
    const maxPnlDate = maxPnlEntry.date;

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

      // Get the daily total we calculated earlier
      const dailyTotal = dailyTotals[dayIndex].total;
      const dailyTotalClass = dailyTotal > 0 ? 'profit' : dailyTotal < 0 ? 'loss' : 'neutral';
      const dailyTotalFormatted = dailyTotal === 0 ? '₹0' : `₹${dailyTotal.toLocaleString()}`;

      // Highlight the max PnL row
      const isMaxPnlDay = dailyTotal === maxPnl;
      const rowClass = isMaxPnlDay ? 'max-pnl-row' : '';

      return `
        <tr class="${rowClass}">
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
            <span class="pnl-label-new">🏆 Max PnL</span>
            <span class="pnl-value-new ${maxPnl >= 0 ? 'profit' : 'loss'}">₹${maxPnl.toLocaleString()}</span>
            <span class="pnl-date-new">📅 ${maxPnlDate}</span>
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
                    <th class="total-pnl-header">💰 Total PnL</th>
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
  },

  loadCustomStrategyForm(container) {
    container.innerHTML = `
      <div class="strategy-form-container">
        <div class="strategy-builder">
          <div class="strategy-header">
            <h3>New Strategy</h3>
            <div class="header-actions">
              <button type="button" id="clear-strategy-btn" class="clear-trades-btn">Clear New Trades</button>
            </div>
          </div>
          
          <div class="strategy-summary">
            <div class="trade-counter">
              <input type="checkbox" id="select-all-trades" checked>
              <span id="trade-count">1 trade selected</span>
            </div>
          </div>
          
          <div class="trades-table">
            <div class="table-header">
              <div class="col-check"></div>
              <div class="col-bs">B/S</div>
              <div class="col-expiry">Expiry</div>
              <div class="col-strike">Strike</div>
              <div class="col-type">Type</div>
              <div class="col-lots">Lots</div>
              <div class="col-premium">Premium</div>
              <div class="col-actions"></div>
            </div>
            
            <div id="trades-container">
              <!-- Dynamic trades will be added here -->
            </div>
          </div>
          
          <div class="action-buttons">
            <button type="button" class="add-edit-btn" onclick="App.addStrategyTrade()">Add/Edit</button>
            <button type="button" id="analyze-strategy-btn" class="buy-btn">Analyze</button>
          </div>
        </div>
      </div>
      
      <div class="strategy-results-container">
        <div id="api-result"></div>
      </div>
    `;

    // Initialize with one trade
    this.addStrategyTrade();
    
    // Add event listeners
    document.getElementById('clear-strategy-btn').addEventListener('click', () => this.clearStrategyLegs());
    document.getElementById('analyze-strategy-btn').addEventListener('click', () => this.analyzeCustomStrategy());
    document.getElementById('select-all-trades').addEventListener('change', this.toggleAllTrades.bind(this));
  },

  addStrategyTrade() {
    const container = document.getElementById('trades-container');
    const tradeIndex = container.children.length;
    
    // Set default expiry to tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const defaultExpiry = tomorrow.toISOString().split('T')[0];
    
    const tradeHtml = `
      <div class="trade-row" data-trade-index="${tradeIndex}">
        <div class="col-check">
          <input type="checkbox" name="trade_selected_${tradeIndex}" checked>
        </div>
        
        <div class="col-bs">
          <select name="action_${tradeIndex}" class="bs-select" required>
            <option value="BUY" selected>B</option>
            <option value="SELL">S</option>
          </select>
        </div>
        
        <div class="col-expiry">
          <input type="date" name="expiry_${tradeIndex}" value="${defaultExpiry}" required>
        </div>
        
        <div class="col-strike">
          <div class="strike-controls">
            <button type="button" class="strike-btn minus" onclick="App.adjustStrike(${tradeIndex}, -100)">−</button>
            <input type="number" name="strike_${tradeIndex}" value="25600" step="50" required>
            <button type="button" class="strike-btn plus" onclick="App.adjustStrike(${tradeIndex}, 100)">+</button>
          </div>
        </div>
        
        <div class="col-type">
          <select name="option_type_${tradeIndex}" class="type-select" required>
            <option value="CE" selected>CE</option>
            <option value="PE">PE</option>
          </select>
        </div>
        
        <div class="col-lots">
          <select name="quantity_${tradeIndex}" class="lots-select" required>
            <option value="75" selected>1</option>
            <option value="150">2</option>
            <option value="225">3</option>
            <option value="300">4</option>
            <option value="375">5</option>
            <option value="450">6</option>
            <option value="525">7</option>
            <option value="600">8</option>
            <option value="750">10</option>
            <option value="900">12</option>
            <option value="1125">15</option>
            <option value="1500">20</option>
          </select>
        </div>
        
        <div class="col-premium">
          <input type="number" name="premium_${tradeIndex}" placeholder="0.0" step="0.01" class="premium-input">
        </div>
        
        <div class="col-actions">
          <button type="button" class="action-btn menu-btn">≡</button>
          <button type="button" class="action-btn delete-btn" onclick="App.removeStrategyTrade(${tradeIndex})">🗑</button>
        </div>
        
        <input type="hidden" name="symbol_${tradeIndex}" value="NIFTY">
      </div>
    `;
    
    container.insertAdjacentHTML('beforeend', tradeHtml);
    
    // Add event listeners for real-time updates
    const newRow = container.lastElementChild;
    newRow.querySelectorAll('input, select').forEach(field => {
      field.addEventListener('change', () => this.updateStrategyTotals());
      field.addEventListener('input', () => this.updateStrategyTotals());
    });
    
    this.updateTradeCount();
    this.updateStrategyTotals();
  },

  removeStrategyTrade(tradeIndex) {
    const tradeElement = document.querySelector(`[data-trade-index="${tradeIndex}"]`);
    if (tradeElement) {
      tradeElement.remove();
      this.reindexStrategyTrades();
      this.updateTradeCount();
      this.updateStrategyTotals();
    }
  },

  reindexStrategyTrades() {
    const trades = document.querySelectorAll('.trade-row');
    trades.forEach((trade, index) => {
      trade.setAttribute('data-trade-index', index);
      
      // Update all field names and onclick handlers
      const fields = trade.querySelectorAll('input, select');
      fields.forEach(field => {
        const nameAttr = field.getAttribute('name');
        if (nameAttr && nameAttr.includes('_')) {
          const fieldType = nameAttr.split('_')[0];
          field.setAttribute('name', `${fieldType}_${index}`);
        }
      });
      
      // Update onclick handlers for buttons
      const deleteBtn = trade.querySelector('.delete-btn');
      if (deleteBtn) {
        deleteBtn.setAttribute('onclick', `App.removeStrategyTrade(${index})`);
      }
      
      const minusBtn = trade.querySelector('.strike-btn.minus');
      const plusBtn = trade.querySelector('.strike-btn.plus');
      if (minusBtn) minusBtn.setAttribute('onclick', `App.adjustStrike(${index}, -100)`);
      if (plusBtn) plusBtn.setAttribute('onclick', `App.adjustStrike(${index}, 100)`);
    });
  },

  adjustStrike(tradeIndex, adjustment) {
    const strikeInput = document.querySelector(`[name="strike_${tradeIndex}"]`);
    if (strikeInput) {
      const currentValue = parseInt(strikeInput.value) || 25600;
      strikeInput.value = currentValue + adjustment;
      this.updateStrategyTotals();
    }
  },

  clearStrategyLegs() {
    document.getElementById('trades-container').innerHTML = '';
    this.addStrategyTrade();
    this.updateTradeCount();
    this.updateStrategyTotals();
  },

  updateTradeCount() {
    const tradeCount = document.querySelectorAll('.trade-row').length;
    document.getElementById('trade-count').textContent = `${tradeCount} trade${tradeCount !== 1 ? 's' : ''} selected`;
  },

  toggleAllTrades(e) {
    const checkboxes = document.querySelectorAll('[name*="trade_selected_"]');
    checkboxes.forEach(checkbox => {
      checkbox.checked = e.target.checked;
    });
  },

  updateStrategyTotals() {
    // This function is kept for compatibility but no longer displays totals
    // since the price display section has been removed
  },

  async analyzeCustomStrategy() {
    const legs = this.collectStrategyLegs();
    
    if (legs.length === 0) {
      UIManager.displayResult('api-result', 'Please add at least one strategy leg.', true);
      return;
    }

    // Validate all legs
    for (let i = 0; i < legs.length; i++) {
      const leg = legs[i];
      if (!leg.symbol || !leg.expiry || !leg.strike || !leg.option_type || !leg.action || !leg.quantity) {
        UIManager.displayResult('api-result', `Please fill all required fields for Leg ${i + 1}.`, true);
        return;
      }
    }

    const payload = { legs };
    
    UIManager.displayResult('api-result', 'Analyzing strategy...');
    
    try {
      const result = await ApiService.analyzeCustomStrategy(payload);
      if (result.success) {
        this.displayStrategyAnalysisResult(result.data);
      } else {
        UIManager.displayResult('api-result', result.error || 'Analysis failed', true);
      }
    } catch (error) {
      UIManager.displayResult('api-result', `Error: ${error.message}`, true);
    }
  },

  collectStrategyLegs() {
    const legs = [];
    const tradeElements = document.querySelectorAll('.trade-row');
    
    tradeElements.forEach((tradeElement, index) => {
      const selected = tradeElement.querySelector(`[name="trade_selected_${index}"]`)?.checked;
      
      if (selected) {
        const symbol = tradeElement.querySelector(`[name="symbol_${index}"]`)?.value || 'NIFTY';
        const expiryDate = tradeElement.querySelector(`[name="expiry_${index}"]`)?.value;
        const strike = tradeElement.querySelector(`[name="strike_${index}"]`)?.value;
        const option_type = tradeElement.querySelector(`[name="option_type_${index}"]`)?.value;
        const action = tradeElement.querySelector(`[name="action_${index}"]`)?.value;
        const quantity = tradeElement.querySelector(`[name="quantity_${index}"]`)?.value;
        const premium = tradeElement.querySelector(`[name="premium_${index}"]`)?.value;
        
        if (symbol && expiryDate && strike && option_type && action && quantity) {
          // Convert date from YYYY-MM-DD to DD-MMM-YYYY format
          const dateObj = new Date(expiryDate);
          const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
          const formattedExpiry = `${String(dateObj.getDate()).padStart(2, '0')}-${months[dateObj.getMonth()]}-${dateObj.getFullYear()}`;
          
          const leg = {
            symbol: symbol.trim(),
            expiry: formattedExpiry,
            strike: parseFloat(strike),
            option_type: option_type,
            action: action,
            quantity: parseInt(quantity)
          };
          
          if (premium && parseFloat(premium) > 0) {
            leg.premium = parseFloat(premium);
          }
          
          legs.push(leg);
        }
      }
    });
    
    return legs;
  },

  displayStrategyAnalysisResult(data) {
    const resultDiv = document.getElementById('api-result');
    
    if (!data || !data.data) {
      resultDiv.innerHTML = '<div class="error">Invalid response format</div>';
      return;
    }

    const analysis = data.data;
    
    // Update premium values in the form with the returned values
    this.updatePremiumsFromAnalysis(analysis.legs);
    
    const maxProfitDisplay = typeof analysis.max_profit === 'number' 
      ? `₹${analysis.max_profit.toLocaleString()}` 
      : analysis.max_profit;
    
    const maxLossDisplay = typeof analysis.max_loss === 'number' 
      ? `₹${analysis.max_loss.toLocaleString()}` 
      : analysis.max_loss;

    const breakevenPoints = analysis.breakeven_points || [];
    const breakevenDisplay = breakevenPoints.length > 0 
      ? breakevenPoints.map(bp => `₹${bp.toLocaleString()}`).join(', ')
      : 'None';

    const legsDisplay = analysis.legs.map((leg, index) => `
      <tr>
        <td>Leg ${index + 1}</td>
        <td>${leg.symbol}</td>
        <td>${leg.strike}</td>
        <td>${leg.option_type}</td>
        <td>${leg.action}</td>
        <td>${leg.quantity}</td>
        <td>₹${(leg.premium || 0).toLocaleString()}</td>
      </tr>
    `).join('');

    // Create a unique canvas ID for this analysis
    const canvasId = `payoff-chart-${Date.now()}`;

    resultDiv.innerHTML = `
      <div class="strategy-analysis-result">
        <h4>Strategy Analysis Results</h4>
        
        <div class="strike-card">
          <div class="strike-card-header">
            <span>Analysis Summary</span>
          </div>
          <div class="strike-card-body">
            <div class="strike-card-section metrics">
              <div class="section-title">📊 Key Metrics</div>
              <div class="metric-row">
                <span>Breakeven Points</span>
                <span>${breakevenDisplay}</span>
              </div>
              <div class="metric-row">
                <span>Max Profit</span>
                <span class="profit">${maxProfitDisplay}</span>
              </div>
              <div class="metric-row">
                <span>Max Loss</span>
                <span class="loss">${maxLossDisplay}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="payoff-chart-container">
          <h5>Payoff Graph</h5>
          <canvas id="${canvasId}" width="800" height="400"></canvas>
        </div>
      </div>
    `;

    // Draw the payoff chart
    this.drawPayoffChart(canvasId, analysis);
  },

  updatePremiumsFromAnalysis(returnedLegs) {
    // Get all trade rows in the form
    const tradeElements = document.querySelectorAll('.trade-row');
    
    // Create a mapping of analyzed legs based on their properties
    const legMap = new Map();
    returnedLegs.forEach((leg, index) => {
      // Create a unique key based on symbol, expiry, strike, option_type, and action
      const key = `${leg.symbol}_${leg.expiry}_${leg.strike}_${leg.option_type}_${leg.action}`;
      legMap.set(key, leg);
    });
    
    // Update premium fields in the form
    tradeElements.forEach((tradeElement, index) => {
      const selected = tradeElement.querySelector(`[name="trade_selected_${index}"]`)?.checked;
      
      if (selected) {
        const symbol = tradeElement.querySelector(`[name="symbol_${index}"]`)?.value || 'NIFTY';
        const expiryDate = tradeElement.querySelector(`[name="expiry_${index}"]`)?.value;
        const strike = tradeElement.querySelector(`[name="strike_${index}"]`)?.value;
        const option_type = tradeElement.querySelector(`[name="option_type_${index}"]`)?.value;
        const action = tradeElement.querySelector(`[name="action_${index}"]`)?.value;
        const premiumInput = tradeElement.querySelector(`[name="premium_${index}"]`);
        
        if (expiryDate && strike && option_type && action && premiumInput) {
          // Convert date from YYYY-MM-DD to DD-MMM-YYYY format to match the API response
          const dateObj = new Date(expiryDate);
          const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
          const formattedExpiry = `${String(dateObj.getDate()).padStart(2, '0')}-${months[dateObj.getMonth()]}-${dateObj.getFullYear()}`;
          
          // Create the key to match against returned legs
          const key = `${symbol.trim()}_${formattedExpiry}_${parseFloat(strike)}_${option_type}_${action}`;
          
          // Find the matching leg in the returned data
          const matchingLeg = legMap.get(key);
          if (matchingLeg && matchingLeg.premium) {
            // Update the premium input field
            premiumInput.value = matchingLeg.premium.toFixed(2);
            
            // Trigger change event for any listeners
            premiumInput.dispatchEvent(new Event('change'));
          }
        }
      }
    });
    
    // No longer need to update totals since the display was removed
  },

  drawPayoffChart(canvasId, analysis) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !analysis.details?.payoff_curve) return;

    const ctx = canvas.getContext('2d');
    const { prices, payoffs } = analysis.details.payoff_curve;
    
    if (!prices || !payoffs || prices.length === 0) return;

    const width = canvas.width;
    const height = canvas.height;
    const padding = 60;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Set up chart dimensions
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    // Find min/max values for scaling
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const minPayoff = Math.min(...payoffs);
    const maxPayoff = Math.max(...payoffs);
    
    // Add some padding to the payoff range
    const payoffRange = maxPayoff - minPayoff;
    const adjustedMinPayoff = minPayoff - payoffRange * 0.1;
    const adjustedMaxPayoff = maxPayoff + payoffRange * 0.1;
    
    // Scale functions
    const scaleX = (price) => padding + ((price - minPrice) / (maxPrice - minPrice)) * chartWidth;
    const scaleY = (payoff) => padding + ((adjustedMaxPayoff - payoff) / (adjustedMaxPayoff - adjustedMinPayoff)) * chartHeight;
    
    // Draw grid lines
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1;
    
    // Vertical grid lines (price)
    for (let i = 0; i <= 10; i++) {
      const price = minPrice + (maxPrice - minPrice) * (i / 10);
      const x = scaleX(price);
      ctx.beginPath();
      ctx.moveTo(x, padding);
      ctx.lineTo(x, height - padding);
      ctx.stroke();
    }
    
    // Horizontal grid lines (payoff)
    for (let i = 0; i <= 10; i++) {
      const payoff = adjustedMinPayoff + (adjustedMaxPayoff - adjustedMinPayoff) * (i / 10);
      const y = scaleY(payoff);
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
    }
    
    // Draw zero line
    const zeroY = scaleY(0);
    ctx.strokeStyle = '#374151';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, zeroY);
    ctx.lineTo(width - padding, zeroY);
    ctx.stroke();
    
    // Draw payoff curve
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    for (let i = 0; i < prices.length; i++) {
      const x = scaleX(prices[i]);
      const y = scaleY(payoffs[i]);
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    
    // Fill profit area (above zero line)
    ctx.fillStyle = 'rgba(16, 185, 129, 0.2)';
    ctx.beginPath();
    ctx.moveTo(padding, zeroY);
    
    for (let i = 0; i < prices.length; i++) {
      const x = scaleX(prices[i]);
      const y = Math.min(scaleY(payoffs[i]), zeroY); // Cap at zero line
      ctx.lineTo(x, y);
    }
    
    ctx.lineTo(width - padding, zeroY);
    ctx.closePath();
    ctx.fill();
    
    // Fill loss area (below zero line)
    ctx.fillStyle = 'rgba(239, 68, 68, 0.2)';
    ctx.beginPath();
    ctx.moveTo(padding, zeroY);
    
    for (let i = 0; i < prices.length; i++) {
      const x = scaleX(prices[i]);
      const y = Math.max(scaleY(payoffs[i]), zeroY); // Cap at zero line
      ctx.lineTo(x, y);
    }
    
    ctx.lineTo(width - padding, zeroY);
    ctx.closePath();
    ctx.fill();
    
    // Draw breakeven points
    if (analysis.breakeven_points && analysis.breakeven_points.length > 0) {
      ctx.fillStyle = '#f59e0b';
      ctx.strokeStyle = '#d97706';
      ctx.lineWidth = 2;
      
      analysis.breakeven_points.forEach(breakeven => {
        const x = scaleX(breakeven);
        const y = scaleY(0);
        
        // Draw breakeven point
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
        
        // Draw vertical line
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.setLineDash([5, 5]);
        ctx.stroke();
        ctx.setLineDash([]);
      });
    }
    
    // Add axis labels
    ctx.fillStyle = '#374151';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    
    // X-axis labels (prices)
    for (let i = 0; i <= 5; i++) {
      const price = minPrice + (maxPrice - minPrice) * (i / 5);
      const x = scaleX(price);
      ctx.fillText(`₹${Math.round(price).toLocaleString()}`, x, height - padding + 20);
    }
    
    // Y-axis labels (payoffs)
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const payoff = adjustedMinPayoff + (adjustedMaxPayoff - adjustedMinPayoff) * (i / 5);
      const y = scaleY(payoff);
      ctx.fillText(`₹${Math.round(payoff).toLocaleString()}`, padding - 10, y + 4);
    }
    
    // Add axis titles
    ctx.textAlign = 'center';
    ctx.font = 'bold 14px Inter, sans-serif';
    ctx.fillText('Underlying Price', width / 2, height - 10);
    
    ctx.save();
    ctx.translate(15, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Profit/Loss', 0, 0);
    ctx.restore();
    
    // Add title
    ctx.textAlign = 'center';
    ctx.font = 'bold 16px Inter, sans-serif';
    ctx.fillText('Strategy Payoff Diagram', width / 2, 25);
  }
};

// Logout handler
document.getElementById('logoutButton').addEventListener('click', () => {
  localStorage.removeItem('access_token');
  showSection('login-section');
});

// Dashboard API button handler
document.querySelectorAll('.api-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const api = btn.getAttribute('data-api');
    loadApiForm(api);
  });
});

// Back to dashboard
document.getElementById('backToDashboard').addEventListener('click', () => {
  showSection('dashboard-section');
  document.getElementById('api-form-container').innerHTML = '';
  document.getElementById('api-result').innerHTML = '';
});

// Load API form dynamically
function loadApiForm(api) {
  showSection('api-form-section');
  const container = document.getElementById('api-form-container');
  container.innerHTML = ''; // Clear previous

  if (api === 'volatility') {
    container.innerHTML = `
      <h3>Volatility API</h3>
      <form id="volForm">
        <input type="text" id="symbol" placeholder="Symbol" required>
        <input type="date" id="end_date" required>
        <input type="number" id="years_of_data" placeholder="Years of Data" required>
        <button type="submit">Submit</button>
      </form>
    `;
    document.getElementById('volForm').onsubmit = async function(e) {
      e.preventDefault();
      const payload = {
        symbol: document.getElementById('symbol').value,
        end_date: document.getElementById('end_date').value,
        years_of_data: document.getElementById('years_of_data').value
      };
      await callApi('/api/v1_0/fyres/volatility', payload);
    };
  }
  else if (api === 'simulation') {
    container.innerHTML = `
      <h3>Simulation API</h3>
      <form id="simForm">
        <input type="text" id="sim_symbol" placeholder="Symbol" required>
        <button type="submit">Run Simulation</button>
      </form>
    `;
    document.getElementById('simForm').onsubmit = async function(e) {
      e.preventDefault();
      const symbol = document.getElementById('sim_symbol').value;
      await callApi(`/api/v1_0/strategy/simulation?symbol=${encodeURIComponent(symbol)}`);
    };
  }
  else if (api === 'transactions') {
    container.innerHTML = `
      <h3>Transactions API</h3>
      <form id="transForm">
        <input type="text" id="trans_symbol" placeholder="Symbol" required>
        <button type="submit">Get Transactions</button>
      </form>
    `;
    document.getElementById('transForm').onsubmit = async function(e) {
      e.preventDefault();
      const symbol = document.getElementById('trans_symbol').value;
      await callApi(`/api/v1_0/transactions?symbol=${encodeURIComponent(symbol)}`);
    };
  }
  else if (api === 'strike-performance') {
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
    document.getElementById('strikeForm').onsubmit = async function(e) {
      e.preventDefault();
      const resultDiv = document.getElementById('api-result');
      resultDiv.innerHTML = ''; // Clear previous results

      const symbol = document.getElementById('sp_symbol').value;
      const endDateStr = document.getElementById('sp_end_date').value;
      const numMonths = parseInt(document.getElementById('sp_years_of_data').value, 10);

      // --- DATE LOGIC ---
      const months = [];
      const startDate = new Date(endDateStr);
      startDate.setUTCDate(1);
      startDate.setUTCMonth(startDate.getUTCMonth() - 1);

      for (let i = 0; i < numMonths; i++) {
        months.push({
          mm: String(startDate.getUTCMonth() + 1).padStart(2, '0'),
          year: startDate.getFullYear()
        });
        startDate.setUTCMonth(startDate.getUTCMonth() - 1);
      }
      months.reverse();

      const token = localStorage.getItem('access_token');

      // Fetch and display each month sequentially
      for (const m of months) {
        const mm = m.mm;
        const yy = String(m.year).slice(-2);
        
        const volatilityUrl = `/api/v1_0/fyres/volatility_of_month/${mm}/${yy}/${encodeURIComponent(symbol)}`;
        const simulationUrl = `/api/v1_0/strategy/monthly_volatility_simulation/${mm}/${yy}`;

        // Show loading for this month
        const loadingId = `loading-${mm}-${m.year}`;
        resultDiv.innerHTML += `<div id="${loadingId}">Loading ${mm}/${m.year}...</div>`;

        try {
          // Call both APIs
          const [volRes, simRes] = await Promise.all([
            fetch(API_BASE_URL + volatilityUrl, {
              method: 'GET',
              headers: { 'Authorization': `Bearer ${token}` }
            }),
            fetch(API_BASE_URL + simulationUrl, {
              method: 'GET',
              headers: { 'Authorization': `Bearer ${token}` }
            })
          ]);

          const volData = await volRes.json();
          const simData = await simRes.json();

          if (volRes.ok) {
            // Create the complete HTML with both volatility data and PnL table
            const monthHtml = createMonthSection(mm, m.year, volData, simData, null);
            
            // Replace the loading div
            const loadingDiv = document.getElementById(loadingId);
            loadingDiv.outerHTML = monthHtml;
          } else {
            // Handle volatility API error
            const loadingDiv = document.getElementById(loadingId);
            loadingDiv.outerHTML = `<div class="date-header">${mm}/${m.year}</div><span class="error">${volData.detail || 'API Error'}</span>`;
          }
        } catch (err) {
          // Handle network error
          const loadingDiv = document.getElementById(loadingId);
          if(loadingDiv) loadingDiv.outerHTML = `<div class="date-header">${mm}/${m.year}</div><span class="error">Network error</span>`;
        }
      }
    };
  }
}

// Call API and display result
async function callApi(endpoint, payload = null) {
  const resultDiv = document.getElementById('api-result');
  resultDiv.textContent = 'Loading...';
  try {
    const token = localStorage.getItem('access_token');
    const opts = {
      method: payload ? 'POST' : 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    };
    if (payload) opts.body = JSON.stringify(payload);
    const res = await fetch(API_BASE_URL + endpoint, opts);
    const data = await res.json();
    if (res.ok) {
      resultDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    } else {
      resultDiv.innerHTML = `<span class="error">${data.detail || 'API Error'}</span>`;
    }
  } catch (err) {
    resultDiv.innerHTML = `<span class="error">Network error</span>`;
  }
}

async function callStrikePerformanceApi(endpoint, payload) {
  const resultDiv = document.getElementById('api-result');
  resultDiv.textContent = 'Loading...';
  try {
    const token = localStorage.getItem('access_token');
    const res = await fetch(API_BASE_URL + endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      resultDiv.innerHTML = renderStrikePerformanceTable(data);
    } else {
      resultDiv.innerHTML = `<span class="error">${data.detail || 'API Error'}</span>`;
    }
  } catch (err) {
    resultDiv.innerHTML = `<span class="error">Network error</span>`;
  }
}

// Pretty table renderer
function renderStrikePerformanceTable(data) {
  if (!data || typeof data !== 'object') return '<span class="error">No data</span>';

  // Extract values
  const symbol = data.symbol || '';
  const targetMonth = data.target_month || '';
  const spot = data.volatility_metrics?.spot ?? '';
  const metrics = data.volatility_metrics || {};
  const strikes = data.strikes || {};
  const vbs = strikes.volatility_based_strikes?.["range_1.5sd"] || {};
  const sbs = strikes.spot_based_strikes || {};

  return `
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
          <div>Lower SELL PE: <b>${vbs.lower_strike ?? '-'}</b>, Upper SELL CE: <b>${vbs.upper_strike ?? '-'}</b></div>
        </div>
        <div class="strike-row">
          <div class="strike-label">Spot Based</div>
          <div>Lower BUY PE: <b>${sbs.lower_strike ?? '-'}</b>, Upper BUY CE: <b>${sbs.upper_strike ?? '-'}</b></div>
        </div>
      </div>
    </div>
  </div>
  `;
}

// Add this new function (without chart section)
function renderStrikePerformanceTableOnly(data) {
  if (!data || typeof data !== 'object') return '<span class="error">No data</span>';

  // Extract values
  const symbol = data.symbol || '';
  const targetMonth = data.target_month || '';
  const spot = data.volatility_metrics?.spot ?? '';
  const metrics = data.volatility_metrics || {};
  const strikes = data.strikes || {};
  const vbs = strikes.volatility_based_strikes?.["range_1.5sd"] || {};
  const sbs = strikes.spot_based_strikes || {};

  return `
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
          <div>Lower SELL PE: <b>${vbs.lower_strike ?? '-'}</b>, Upper SELL CE: <b>${vbs.upper_strike ?? '-'}</b></div>
        </div>
        <div class="strike-row">
          <div class="strike-label">Spot Based</div>
          <div>Lower BUY PE: <b>${sbs.lower_strike ?? '-'}</b>, Upper BUY CE: <b>${sbs.upper_strike ?? '-'}</b></div>
        </div>
      </div>
    </div>
  </div>
  `;
}

function createMonthSection(mm, year, volData, simData, canvasId) {
  const hasSimData = simData && simData.status === "success";
  
  // Build the complete strike card with integrated PnL table
  const symbol = volData.symbol || '';
  const targetMonth = volData.target_month || '';
  const spot = volData.volatility_metrics?.spot ?? '';
  const metrics = volData.volatility_metrics || {};
  const strikes = volData.strikes || {};
  const vbs = strikes.volatility_based_strikes?.["range_1.5sd"] || {};
  const sbs = strikes.spot_based_strikes || {};

  const pnlSection = hasSimData ? createPnlTable(simData.data) : `
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
            <div>Lower SELL PE: <b>${vbs.lower_strike ?? '-'}</b>, Upper SELL CE: <b>${vbs.upper_strike ?? '-'}</b></div>
          </div>
          <div class="strike-row">
            <div class="strike-label">Spot Based</div>
            <div>Lower BUY PE: <b>${sbs.lower_strike ?? '-'}</b>, Upper BUY CE: <b>${sbs.upper_strike ?? '-'}</b></div>
          </div>
        </div>
      </div>
      ${pnlSection}
    </div>
  `;
}

// This duplicate function has been removed - using the updated one above

function renderPnlChart(apiData, canvasId) {
  console.log("renderPnlChart called with canvasId:", canvasId);
  
  const canvas = document.getElementById(canvasId);
  if (!canvas) {
    console.error(`Canvas element with id ${canvasId} not found!`);
    return;
  }
  
  // Check if data is valid
  if (!apiData || !apiData.daily_pnl) {
    console.warn("Invalid data for chart rendering:", apiData);
    return;
  }

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

    // Get the daily total we calculated earlier
    const dailyTotal = dailyTotals[dayIndex].total;
    const dailyTotalClass = dailyTotal > 0 ? 'profit' : dailyTotal < 0 ? 'loss' : 'neutral';
    const dailyTotalFormatted = dailyTotal === 0 ? '₹0' : `₹${dailyTotal.toLocaleString()}`;

    // Highlight the max PnL row
    const isMaxPnlDay = dailyTotal === maxPnl;
    const rowClass = isMaxPnlDay ? 'max-pnl-row' : '';

    return `
      <tr class="${rowClass}">
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
          <span class="pnl-label-new">� Max PnL</span>
          <span class="pnl-value-new ${maxPnl >= 0 ? 'profit' : 'loss'}">₹${maxPnl.toLocaleString()}</span>
          <span class="pnl-date-new">📅 ${maxPnlDate}</span>
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
                  <th class="date-header" style="color: #3b82f6;">📅 Date</th>
                  ${tableHeaders}
                  <th class="total-pnl-header">💰 Total PnL</th>
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

// --- COMPACT CARD CREATION --- //

// Update the createStrikeCard function for compact display:

function createStrikeCard(apiData) {
  const { month, symbol, target_month, spot, volatility_metrics, strikes } = apiData;

  const pnlSection = createPnlTable(apiData);

  return `
    <div class="date-header">${month}</div>
    <div class="strike-card">
      <div class="strike-card-header">
        <span><b>Symbol:</b> ${symbol}</span>
        <span><b>Target Month:</b> ${target_month}</span>
        <span><b>Spot:</b> ${spot}</span>
      </div>
      <div class="strike-card-body">
        <div class="metrics-strikes-container">
          <div class="strike-card-section metrics">
            <div class="section-title">📊 Volatility Metrics</div>
            ${Object.entries(volatility_metrics).map(([key, value]) => `
              <div class="metric-row">
                <span>${key.replace(/_/g, ' ')}</span>
                <span>${typeof value === 'number' ? value.toFixed(4) : value}</span>
              </div>
            `).join('')}
          </div>
          
          <div class="strike-card-section strikes">
            <div class="section-title">🎯 Strikes</div>
            ${Object.entries(strikes).map(([key, value]) => `
              <div class="strike-row">
                <div class="strike-label">${key.replace(/_/g, ' ')}</div>
                ${typeof value === 'object' ? 
                  Object.entries(value).map(([k, v]) => `
                    <div class="metric-row">
                      <span>${k}</span>
                      <span>${v}</span>
                    </div>
                  `).join('') :
                  `<div class="metric-row"><span></span><span>${value}</span></div>`
                }
              </div>
            `).join('')}
          </div>
        </div>
        
        ${pnlSection}
      </div>
    </div>
  `;
}

// --- END OF COMPACT CARD CREATION --- //

function renderPnlChart(apiData, canvasId) {
  console.log("renderPnlChart called with canvasId:", canvasId);
  
  const canvas = document.getElementById(canvasId);
  if (!canvas) {
    console.error(`Canvas element with id ${canvasId} not found!`);
    return;
  }
  
  // Check if data is valid
  if (!apiData || !apiData.daily_pnl) {
    console.warn("Invalid data for chart rendering:", apiData);
    return;
  }

  const dailyPnl = apiData.daily_pnl;
  if (dailyPnl.length === 0) {
    console.warn("No daily PnL data available");
    return;
  }

  // Clear any existing chart on this canvas
  const existingChart = Chart.getChart(canvas);
  if (existingChart) {
    console.log("Destroying existing chart on canvas:", canvasId);
    existingChart.destroy();
  }

  const labels = dailyPnl.map(day => day.date.substring(5, 10)); // Format: MM-DD

  const positions = apiData.positions;
  const datasets = positions.map((pos, index) => {
    const pnlData = dailyPnl.map(day => day.unrealised[index]?.pnl ?? 0);
    return {
      label: `${pos.strike} ${pos.option_type}`,
      data: pnlData,
      fill: false,
      tension: 0.1,
      borderColor: `hsl(${index * 60}, 70%, 50%)`,
      backgroundColor: `hsla(${index * 60}, 70%, 50%, 0.1)`
    };
  });

  try {
    const chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top'
          },
          title: {
            display: true,
            text: 'Daily PnL per Position'
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Date'
            }
          },
          y: {
            title: {
              display: true,
              text: 'Profit / Loss (PnL)'
            }
          }
        }
      }
    });
    console.log("Chart successfully rendered for:", canvasId);
    
    // Store chart reference for debugging
    canvas._chartInstance = chart;
    
  } catch (error) {
    console.error("Error rendering chart for", canvasId, ":", error);
  }
}

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

// Transaction Management Functions
App.loadTransactions = async function() {
  const container = document.getElementById('transactions-container');
  if (!container) return;
  
  container.innerHTML = '<div class="loading-transactions">Loading transactions...</div>';
  
  try {
    console.log('Loading transactions...');
    const result = await ApiService.getActiveTransactions();
    console.log('Transaction result:', result);
    
    if (result.success && result.data) {
      this.displayTransactions(result.data);
    } else {
      container.innerHTML = `<div class="no-transactions">Failed to load transactions: ${result.error || 'Unknown error'}</div>`;
      console.error('Failed to load transactions:', result.error);
    }
  } catch (error) {
    container.innerHTML = '<div class="no-transactions">Error loading transactions</div>';
    console.error('Error loading transactions:', error);
  }
};

App.displayTransactions = function(transactionData) {
  const container = document.getElementById('transactions-container');
  if (!container) return;
  
  // Handle the API response structure
  const transactions = transactionData.data || transactionData;
  
  if (!transactions || transactions.length === 0) {
    container.innerHTML = '<div class="no-transactions">No transactions found. Create your first transaction using the Transactions API!</div>';
    return;
  }
  
  const transactionsHtml = transactions.map(transaction => {
    return `
      <div class="transaction-item" data-transaction-id="${transaction.transaction_id}">
        <div class="transaction-details">
          <div class="transaction-field">
            <div class="label">Symbol</div>
            <div class="value symbol">${transaction.symbol}</div>
          </div>
          <div class="transaction-field">
            <div class="label">Instrument</div>
            <div class="value">${transaction.instrument}</div>
          </div>
          <div class="transaction-field">
            <div class="label">Strike Price</div>
            <div class="value">₹${transaction.strike_price}</div>
          </div>
          <div class="transaction-field">
            <div class="label">Option Type</div>
            <div class="value option-type ${transaction.option_type}">${transaction.option_type}</div>
          </div>
          <div class="transaction-field">
            <div class="label">Lots</div>
            <div class="value">${transaction.lots}</div>
          </div>
          <div class="transaction-field">
            <div class="label">Trade Date</div>
            <div class="value">${this.formatDate(transaction.trade_date)}</div>
          </div>
          <div class="transaction-field">
            <div class="label">Expiry Date</div>
            <div class="value">${this.formatDate(transaction.expiry_date)}</div>
          </div>
        </div>
        <button class="delete-btn" onclick="App.deleteTransaction(${transaction.transaction_id})">
          Delete
        </button>
      </div>
    `;
  }).join('');
  
  container.innerHTML = transactionsHtml;
};

App.deleteTransaction = async function(transactionId) {
  if (!confirm('Are you sure you want to delete this transaction?')) {
    return;
  }
  
  try {
    const result = await ApiService.deleteTransaction(transactionId);
    
    if (result.success) {
      // Remove the transaction from the UI
      const transactionElement = document.querySelector(`[data-transaction-id="${transactionId}"]`);
      if (transactionElement) {
        transactionElement.style.transition = 'all 0.3s ease';
        transactionElement.style.opacity = '0';
        transactionElement.style.transform = 'translateX(-100%)';
        
        setTimeout(() => {
          transactionElement.remove();
          
          // Check if there are any transactions left
          const container = document.getElementById('transactions-container');
          const remainingTransactions = container.querySelectorAll('.transaction-item');
          if (remainingTransactions.length === 0) {
            container.innerHTML = '<div class="no-transactions">No transactions found. Create your first transaction using the Transactions API!</div>';
          }
        }, 300);
      }
    } else {
      alert('Failed to delete transaction: ' + (result.error || 'Unknown error'));
    }
  } catch (error) {
    alert('Error deleting transaction: ' + error.message);
    console.error('Error deleting transaction:', error);
  }
};

App.deleteAllTransactions = async function() {
  if (!confirm('Are you sure you want to delete ALL transactions? This action cannot be undone.')) {
    return;
  }
  
  try {
    console.log('Deleting all transactions...');
    const result = await ApiService.deleteAllTransactions();
    console.log('Delete all result:', result);
    
    if (result.success) {
      // Clear the transactions container and show success message
      const container = document.getElementById('transactions-container');
      if (container) {
        container.innerHTML = '<div class="no-transactions">All transactions have been deleted successfully!</div>';
      }
      
      // Show success message temporarily
      setTimeout(() => {
        if (container) {
          container.innerHTML = '<div class="no-transactions">No transactions found. Create your first transaction using the Transactions API!</div>';
        }
      }, 3000);
    } else {
      alert('Failed to delete all transactions: ' + (result.error || 'Unknown error'));
    }
  } catch (error) {
    alert('Error deleting all transactions: ' + error.message);
    console.error('Error deleting all transactions:', error);
  }
};

App.formatDate = function(dateString) {
  if (!dateString) return 'N/A';
  
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  } catch (error) {
    return dateString;
  }
};

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});