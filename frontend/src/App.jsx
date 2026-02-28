import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Loader2, Sparkles } from 'lucide-react';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_ENDPOINT = `${API_BASE_URL}/api/v1/recommendations`;
const META_ENDPOINT = `${API_BASE_URL}/api/v1/meta/filters`;

function App() {
  const [formData, setFormData] = useState({
    location: '',
    cuisines: '',
    min_rating: 4.0,
    budget_min: 0,
    budget_max: 500
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState({
    restaurants: [],
    summary: '',
    meta: { total_candidates: 0, returned: 0 }
  });

  const [hasSearched, setHasSearched] = useState(false);
  const [metaOptions, setMetaOptions] = useState({
    locations: [],
    cuisines_by_location: {}
  });

  const [dynamicCuisines, setDynamicCuisines] = useState([]);

  // Fetch metadata once
  useEffect(() => {
    const fetchMeta = async () => {
      try {
        const response = await axios.get(META_ENDPOINT);
        const meta = response.data;

        setMetaOptions(meta);

        if (meta.locations?.length > 0) {
          const firstLoc = meta.locations[0];

          setFormData(prev => ({
            ...prev,
            location: firstLoc
          }));

          setDynamicCuisines(
            meta.cuisines_by_location[firstLoc] || []
          );
        }
      } catch (err) {
        console.warn('Metadata service unavailable');
      }
    };

    fetchMeta();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;

    if (name === 'location') {
      setFormData(prev => ({
        ...prev,
        location: value,
        cuisines: ''
      }));

      setDynamicCuisines(
        metaOptions.cuisines_by_location[value] || []
      );

      return;
    }

    setFormData(prev => ({
      ...prev,
      [name]: (name.includes('budget') || name === 'min_rating')
        ? parseFloat(value) || 0
        : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setData({
      restaurants: [],
      summary: '',
      meta: { total_candidates: 0, returned: 0 }
    });

    try {
      const cuisinesArray = formData.cuisines
        ? [formData.cuisines]
        : [];

      const payload = {
        location: formData.location || undefined,
        cuisines: cuisinesArray,
        min_rating: formData.min_rating,
        budget_min: formData.budget_min,
        budget_max: formData.budget_max,
        max_results: 10,
        use_llm: true
      };

      const response = await axios.post(API_ENDPOINT, payload);
      setData(response.data);
      setHasSearched(true); 
    } catch (err) {
      console.error('API Error:', err);
      setError('Failed to fetch recommendations.');
      setHasSearched(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <section className="hero">
        <h1>Find your next meal</h1>
        <p>Set location, rating, and preferences — get AI-powered restaurant recommendations.</p>
      </section>

      <section className="search-card">
        <SearchForm
          formData={formData}
          handleChange={handleChange}
          handleSubmit={handleSubmit}
          loading={loading}
          locations={metaOptions.locations}
          dynamicCuisines={dynamicCuisines}
        />
      </section>

      {error && <div className="error">{error}</div>}

      {loading && (
        <div className="loading-spinner">
          <Loader2 className="animate-spin" size={40} />
        </div>
      )}

      {!loading && data.summary && (
        <InsightCard summary={data.summary} />
      )}

      {!loading && data.restaurants.length > 0 && (
        <>
          <div className="results-header">
            <h2>Recommendations</h2>
            <span className="results-count">{data.meta.returned} results found</span>
          </div>

          <div className="results-list">
            {data.restaurants.map((rest, index) => (
              <RecommendationCard
                key={rest.id}
                restaurant={rest}
                rank={index + 1}
              />
            ))}
          </div>
        </>
      )}

      {!loading && !error && hasSearched && data.restaurants.length === 0 && (
        <div className="no-results">
          {formData.cuisines ? (
            <p>No {formData.cuisines} restaurants found in {formData.location}. Try another cuisine or adjust filters.</p>
          ) : (
            <p>No restaurants found in {formData.location}. Try lowering the rating filter.</p>
          )}
        </div>
      )}
    </div>
  );
}

function SearchForm({ formData, handleChange, handleSubmit, loading, locations, dynamicCuisines }) {
  return (
    <form onSubmit={handleSubmit} className="preference-form">
      <div className="search-grid">

        <div className="input-group">
          <label>Location</label>
          <select
            name="location"
            value={formData.location}
            onChange={handleChange}
            className="select-input"
          >
            <option value="">Select Location</option>
            {locations.map(loc => (
              <option key={loc} value={loc}>{loc}</option>
            ))}
          </select>
        </div>

        <div className="input-group">
          <label>Min Rating</label>
          <input
            type="number"
            name="min_rating"
            step="0.1"
            min="0"
            max="5"
            value={formData.min_rating}
            onChange={handleChange}
          />
        </div>

        <div className="input-group">
          <label>Cuisine (Optional)</label>
          <select
            name="cuisines"
            value={formData.cuisines}
            onChange={handleChange}
            className="select-input"
          >
            <option value="">All Cuisines</option>
            {dynamicCuisines.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div className="input-group">
          <label>Budget (Optional)</label>
          <select
            name="budget_max"
            value={formData.budget_max}
            onChange={handleChange}
          >
            <option value="500">Value (Under ₹500)</option>
            <option value="1500">Moderate (Under ₹1500)</option>
            <option value="3000">Mid-range (Under ₹3000)</option>
            <option value="10000">Premium (No Limit)</option>
          </select>
        </div>

      </div>

      <button type="submit" className="cta-button" disabled={loading}>
        {loading ? 'Analyzing data...' : 'Get recommendations'}
      </button>
    </form>
  );
}

function InsightCard({ summary }) {
  return (
    <div className="insight-card">
      <span className="insight-icon">
        <Sparkles size={18} fill="currentColor" />
      </span>
      <span className="insight-text">
        AI Insight: {summary}
      </span>
    </div>
  );
}

function RecommendationCard({ restaurant, rank }) {
  return (
    <div className="recommendation-card">
      <div className="rank-number">#{rank}</div>
      <div className="card-content">
        <div className="card-header">
          <h3>{restaurant.name}</h3>
          {(restaurant.badges || []).map(badge => (
            <span key={badge} className={`badge ${badge.toLowerCase().replace(' ', '-')}`}>
              {badge}
            </span>
          ))}
        </div>

        <div className="rating-row">
          <strong>★ {restaurant.rating || 'N/A'}/5</strong>
          <span>•</span>
          <span>{restaurant.votes || 0} votes</span>
          <span>•</span>
          <span>₹{restaurant.approx_cost_for_two || '---'} for two</span>
        </div>

        <div className="cuisine-tags">
          {(restaurant.cuisines || []).map(c => (
            <span key={c} className="tag">{c}</span>
          ))}
        </div>

        <p className="explanation">
          "{restaurant.explanation || "Excellent choice based on your preferences."}"
        </p>
      </div>

      <button className="view-details">
        View Details
      </button>
    </div>
  );
}

export default App;