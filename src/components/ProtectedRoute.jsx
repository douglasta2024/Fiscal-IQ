import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ProtectedRoute = ({ children }) => {
    const { user } = useAuth();

    if (!user) {
        // user is not authenticated
        return <Navigate to="/login" replace />;
    }

    return children;
};

export default ProtectedRoute;
