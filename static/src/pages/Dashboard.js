import React, { useState, useEffect } from 'react';
import { Grid, Paper, Typography } from '@mui/material';
import { styled } from '@mui/material/styles';
import { Line } from 'react-chartjs-2';
import MetricCard from '../components/MetricCard';
import { fetchDashboardMetrics } from '../services/api';

const Item = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(2),
  textAlign: 'center',
  color: theme.palette.text.secondary,
}));

function Dashboard() {
  const [metrics, setMetrics] = useState({
    excess_stock: 0,
    obsolete_items: 0,
    returns: 0,
    expiring_soon: 0,
  });

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        const data = await fetchDashboardMetrics();
        setMetrics(data);
      } catch (error) {
        console.error('Error loading dashboard metrics:', error);
      }
    };
    loadMetrics();
  }, []);

  return (
    <Grid container spacing={3}>
      <Grid item xs={12}>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
      </Grid>
      
      <Grid item xs={12} sm={6} md={3}>
        <MetricCard
          title="Excess Stock"
          value={metrics.excess_stock}
          color="#1976d2"
        />
      </Grid>
      
      <Grid item xs={12} sm={6} md={3}>
        <MetricCard
          title="Obsolete Items"
          value={metrics.obsolete_items}
          color="#dc004e"
        />
      </Grid>
      
      <Grid item xs={12} sm={6} md={3}>
        <MetricCard
          title="Returns"
          value={metrics.returns}
          color="#ff9800"
        />
      </Grid>
      
      <Grid item xs={12} sm={6} md={3}>
        <MetricCard
          title="Expiring Soon"
          value={metrics.expiring_soon}
          color="#f44336"
        />
      </Grid>

      <Grid item xs={12}>
        <Item>
          <Typography variant="h6" gutterBottom>
            Allocation History
          </Typography>
          {/* Add Line chart component here */}
        </Item>
      </Grid>
    </Grid>
  );
}

export default Dashboard;
