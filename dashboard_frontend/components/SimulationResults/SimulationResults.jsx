import React, { useState } from 'react';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableRow, 
  Paper, 
  Typography,
  Collapse,
  Box,
  Chip,
  Grid,
  Card,
  CardContent,
  Tabs,
  Tab
} from '@mui/material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './SimulationResults.css';

// Helper function to format PnL with color
const formatPnL = (pnl) => {
  const color = pnl >= 0 ? 'success.main' : 'error.main';
  return (
    <Typography sx={{ color }}>
      {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
    </Typography>
  );
};

// Helper to create a unique ID for each contract
const createContractId = (contract) => {
  if (!contract || !Array.isArray(contract) || contract.length < 5) return 'unknown';
  return `${contract[0]}-${contract[1]}-${contract[2]}-${contract[3]}-${contract[4]}`;
};

// Process simulation data to organize by contract
const processSimulationData = (simulationData) => {
  const contractMap = new Map();
  const dates = [];
  
  simulationData.forEach(dayData => {
    const date = dayData.date;
    dates.push(date);
    
    // Process unrealized positions
    dayData.unrealised.forEach(position => {
      const contractId = createContractId(position.contract);
      if (!contractMap.has(contractId)) {
        contractMap.set(contractId, {
          contract: position.contract,
          dailyPnL: {},
          lots: position.lots
        });
      }
      
      const contractData = contractMap.get(contractId);
      contractData.dailyPnL[date] = position.pnl;
    });
    
    // Process realized positions if they exist
    if (dayData.realised && dayData.realised.length > 0) {
      dayData.realised.forEach(position => {
        const contractId = createContractId(position.contract);
        if (!contractMap.has(contractId)) {
          contractMap.set(contractId, {
            contract: position.contract,
            dailyPnL: {},
            lots: position.lots,
            isRealized: true
          });
        }
        
        const contractData = contractMap.get(contractId);
        contractData.dailyPnL[date] = position.pnl;
        contractData.isRealized = true;
      });
    }
  });
  
  return { contracts: Array.from(contractMap.values()), dates };
};

const SimulationResults = ({ simulationData }) => {
  const [selectedTab, setSelectedTab] = useState(0);
  const [expandedContract, setExpandedContract] = useState(null);
  
  if (!simulationData || simulationData.length === 0) {
    return <Typography>No simulation data available</Typography>;
  }

  const { contracts, dates } = processSimulationData(simulationData);
  
  // Prepare chart data
  const chartData = dates.map(date => {
    const dataPoint = { date };
    
    // Add total daily PnL
    const dayData = simulationData.find(d => d.date === date);
    if (dayData) {
      dataPoint.totalPnL = dayData.total_unrealised_pnl + dayData.total_realized_pnl;
      dataPoint.unrealizedPnL = dayData.total_unrealised_pnl;
      dataPoint.realizedPnL = dayData.total_realized_pnl;
    }
    
    return dataPoint;
  });

  // Group contracts by type for tabs
  const ceContracts = contracts.filter(c => c.contract[1] === 'CE');
  const peContracts = contracts.filter(c => c.contract[1] === 'PE');

  const handleExpandContract = (contractId) => {
    setExpandedContract(expandedContract === contractId ? null : contractId);
  };
  
  const displayContracts = selectedTab === 0 ? ceContracts : peContracts;

  return (
    <Paper sx={{ width: '100%', overflow: 'hidden', p: 2 }}>
      <Typography variant="h5" gutterBottom>
        Simulation Results ({dates[0]} to {dates[dates.length-1]})
      </Typography>

      {/* Summary chart */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6">PnL Summary</Typography>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="totalPnL" stroke="#8884d8" name="Total PnL" />
              <Line type="monotone" dataKey="unrealizedPnL" stroke="#82ca9d" name="Unrealized PnL" />
              <Line type="monotone" dataKey="realizedPnL" stroke="#ff7300" name="Realized PnL" />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Tab for CE/PE selection */}
      <Tabs value={selectedTab} onChange={(e, newValue) => setSelectedTab(newValue)} sx={{ mb: 2 }}>
        <Tab label={`Call Options (CE) - ${ceContracts.length}`} />
        <Tab label={`Put Options (PE) - ${peContracts.length}`} />
      </Tabs>

      {/* Positions Table */}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Contract</TableCell>
            <TableCell>Strike</TableCell>
            <TableCell>Expiry</TableCell>
            <TableCell>Position</TableCell>
            <TableCell>Lots</TableCell>
            {dates.map(date => (
              <TableCell key={date} align="right">{date}</TableCell>
            ))}
            <TableCell align="right">Total PnL</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {displayContracts.map((contract) => {
            const contractId = createContractId(contract.contract);
            let totalPnL = 0;
            
            // Calculate total PnL for this contract
            Object.values(contract.dailyPnL).forEach(pnl => {
              totalPnL += pnl;
            });
            
            return (
              <React.Fragment key={contractId}>
                <TableRow 
                  hover 
                  onClick={() => handleExpandContract(contractId)}
                  sx={{ 
                    cursor: 'pointer',
                    backgroundColor: contract.isRealized ? 'rgba(76, 175, 80, 0.1)' : 'inherit'
                  }}
                >
                  <TableCell>{contract.contract[0]}</TableCell>
                  <TableCell>{contract.contract[2]}</TableCell>
                  <TableCell>{contract.contract[3]}</TableCell>
                  <TableCell>
                    <Chip 
                      size="small" 
                      label={contract.contract[4]} 
                      color={contract.contract[4] === 'LONG' ? 'primary' : 'secondary'}
                    />
                  </TableCell>
                  <TableCell>{contract.lots}</TableCell>
                  {dates.map(date => (
                    <TableCell key={date} align="right">
                      {contract.dailyPnL[date] !== undefined ? 
                        formatPnL(contract.dailyPnL[date]) : 
                        '—'}
                    </TableCell>
                  ))}
                  <TableCell align="right">
                    {formatPnL(totalPnL)}
                  </TableCell>
                </TableRow>
                
                {/* Expanded details */}
                {expandedContract === contractId && (
                  <TableRow>
                    <TableCell colSpan={7 + dates.length}>
                      <Collapse in={expandedContract === contractId} timeout="auto" unmountOnExit>
                        <Box sx={{ p: 2, backgroundColor: 'background.paper' }}>
                          <Typography variant="h6" gutterBottom>
                            Contract Details - {contract.contract[0]} {contract.contract[1]} {contract.contract[2]}
                          </Typography>
                          <ResponsiveContainer width="100%" height={200}>
                            <LineChart 
                              data={dates.map(date => ({
                                date,
                                pnl: contract.dailyPnL[date] || 0
                              }))}
                            >
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="date" />
                              <YAxis />
                              <Tooltip />
                              <Line 
                                type="monotone" 
                                dataKey="pnl" 
                                stroke="#8884d8" 
                                name="Daily PnL"
                                dot={{ stroke: '#8884d8', strokeWidth: 2 }}
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </Box>
                      </Collapse>
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            );
          })}
        </TableBody>
      </Table>
      
      {/* Daily Summary */}
      <Grid container spacing={2} sx={{ mt: 3 }}>
        {simulationData.map((dayData, index) => (
          <Grid item xs={12} sm={6} md={4} key={dayData.date}>
            <Card>
              <CardContent>
                <Typography variant="h6">{dayData.date}</Typography>
                <Typography variant="body2" color="text.secondary">
                  Unrealized PnL: {formatPnL(dayData.total_unrealised_pnl)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Realized PnL: {formatPnL(dayData.total_realized_pnl)}
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 'bold', mt: 1 }}>
                  Daily Total: {formatPnL(dayData.total_unrealised_pnl + dayData.total_realized_pnl)}
                </Typography>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Cumulative Realized: {formatPnL(dayData.cumulative_total_realized_pnl)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Paper>
  );
};

export default SimulationResults;