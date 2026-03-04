import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { supabase } from '../supabaseClient';
import './LoginPage.css'; // Reusing login styles for simplicity

const SignupPage = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    const navigate = useNavigate();

    const handleSignup = async (e) => {
        e.preventDefault();
        setLoading(true);
        setErrorMsg('');
        setSuccessMsg('');

        const { data, error } = await supabase.auth.signUp({
            email,
            password,
        });

        if (error) {
            setErrorMsg(error.message);
        } else {
            setSuccessMsg('Registration successful! Please log in.');
            setTimeout(() => navigate('/login'), 2000);
        }
        setLoading(false);
    };

    return (
        <div className="login-page">
            <div className="login-form">
                <h2>Sign Up</h2>
                {errorMsg && <div className="error-message">{errorMsg}</div>}
                {successMsg && <div className="success-message" style={{ color: 'green', marginBottom: '1rem' }}>{successMsg}</div>}
                <form onSubmit={handleSignup}>
                    <div className="input-group">
                        <label htmlFor="email">Email</label>
                        <input
                            type="email"
                            id="email"
                            name="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>
                    <div className="input-group">
                        <label htmlFor="password">Password</label>
                        <input
                            type="password"
                            id="password"
                            name="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    <button type="submit" className="login-button" disabled={loading}>
                        {loading ? 'Signing up...' : 'Sign Up'}
                    </button>
                </form>
                <p style={{ marginTop: '1rem', textAlign: 'center' }}>
                    Already have an account? <Link to="/login">Log in</Link>
                </p>
            </div>
        </div>
    );
};

export default SignupPage;
