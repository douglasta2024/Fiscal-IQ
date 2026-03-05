import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Header.css';

const Header = () => {
    const location = useLocation();

    // Highlight only the active route
    const getLinkClass = (path) => {
        return `header-link ${location.pathname === path ? 'active' : ''}`;
    };

    return (
        <header className="main-header">
            <div className="header-container">
                <Link to="/" className="header-logo">
                    FIQ
                </Link>
                <nav className="header-nav">
                    <Link to="/" className={getLinkClass('/')}>Home</Link>
                    <Link to="/learn-more" className={getLinkClass('/learn-more')}>Learn More</Link>
                    <Link to="/contact-us" className={getLinkClass('/contact-us')}>Contact Us</Link>
                </nav>
                <div className="header-actions">
                    <Link to="/login" className="header-login-btn">Log in &rarr;</Link>
                </div>
            </div>
        </header>
    );
};

export default Header;
