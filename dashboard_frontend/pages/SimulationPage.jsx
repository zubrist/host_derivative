import React, { useEffect, useState } from 'react';
import { runSimulation } from '../api/simulation'; // Fix the path
import SimulationResults from '../components/SimulationResults';

const SimulationPage = () => {
  const [simulationData, setSimulationData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSimulationData = async () => {
      const accessToken = 'your_access_token_here'; // Replace with actual token logic
      const result = await runSimulation(accessToken);

      if (result.success) {
        setSimulationData(result.data);
      } else {
        setError(result.error);
      }
      setLoading(false);
    };

    fetchSimulationData();
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <h1>Simulation Results</h1>
      {simulationData && <SimulationResults data={simulationData} />}
    </div>
  );
};

export default SimulationPage;