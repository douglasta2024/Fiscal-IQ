import React from 'react';
import { Link } from 'react-router-dom';
import { TypeAnimation } from 'react-type-animation';
import Header from '../components/Header';
import './HomePage.css';

const HomePage = () => {
  return (
    <div className="home-wrapper">
      <Header />
      <div className="home-hero">
        <div className="hero-content">
          <TypeAnimation
            sequence={['Fiscaliq', 2000, 'Intelligence', 2000, 'Finances', 2000]}
            wrapper="h1"
            cursor={true}
            repeat={Infinity}
            className="hero-title"
          />
          <p className="hero-subtitle">
            The next generation platform for tracking, predicting, and elevating your financial future.
          </p>
          <div className="hero-actions">
            <Link to="/signup" className="primary-button">
              Get Started
            </Link>
            <Link to="/learn-more" className="secondary-button">
              Learn How
            </Link>
          </div>
        </div>

        {/* Decorative background elements for aesthetics */}
        <div className="gradient-sphere sphere-1"></div>
        <div className="gradient-sphere sphere-2"></div>
      </div>
    </div>
  );
};

export default HomePage;
