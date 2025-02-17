import React from 'react';
import { Paper, Typography } from '@mui/material';
import { styled } from '@mui/material/styles';

const StyledPaper = styled(Paper)(({ theme, color }) => ({
  padding: theme.spacing(2),
  textAlign: 'center',
  color: theme.palette.text.secondary,
  borderTop: `4px solid ${color}`,
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
}));

function MetricCard({ title, value, color }) {
  return (
    <StyledPaper elevation={3} color={color}>
      <Typography variant="h6" component="h2" gutterBottom>
        {title}
      </Typography>
      <Typography variant="h4" component="p">
        {value}
      </Typography>
    </StyledPaper>
  );
}

export default MetricCard;
