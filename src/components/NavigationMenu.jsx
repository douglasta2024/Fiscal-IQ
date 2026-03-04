import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './NavigationMenu.css';

const NavigationMenu = () => {
    const [isOpen, setIsOpen] = useState(false);
    const { user } = useAuth();
    const location = useLocation();

    // Hide the menu entirely on the Home ('/') and Login ('/login') pages
    if (location.pathname === '/' || location.pathname === '/login') {
        return null;
    }

    // Keep the existing auth check so we don't show the menu on the signup page either
    if (!user) {
        return null;
    }

    const toggleMenu = () => {
        setIsOpen(!isOpen);
    };

    return (
        <>
            <button
                className={`menu-toggle ${isOpen ? 'open' : ''}`}
                onClick={toggleMenu}
                aria-label="Toggle Navigation Menu"
            >
                <span className="bar"></span>
                <span className="bar"></span>
                <span className="bar"></span>
            </button>

            <div className={`side-menu ${isOpen ? 'open' : ''}`}>
                <nav className="menu-links">
                    <Link to="/dashboard" onClick={toggleMenu} className="menu-item">Dashboard</Link>
                    <div className="menu-divider"></div>
                    <Link to="/templates" onClick={toggleMenu} className="menu-item">Templates</Link>
                    <Link to="/settings" onClick={toggleMenu} className="menu-item">Settings</Link>
                </nav>
            </div>

            {/* Overlay to close menu when clicking outside */}
            {isOpen && <div className="menu-overlay" onClick={toggleMenu}></div>}
        </>
    );
};

export default NavigationMenu;
