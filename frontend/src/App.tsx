import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ThumbsUp, ThumbsDown, Loader2, Sparkles, BookOpen, ArrowRight, User, LogOut, Lock } from 'lucide-react';
import './App.css';

const API_BASE = 'http://localhost:8000';

interface Genre { id: number; name: string; }
interface Author { id: number; name: string; }
interface Book { 
  id: number; 
  title: string; 
  synopsis: string; 
  authors: Author[]; 
  genres: Genre[];
}

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<any>(null);
  const [view, setView] = useState<'login' | 'signup' | 'onboarding' | 'recommendations'>('login');
  
  const [genres, setGenres] = useState<Genre[]>([]);
  const [authors, setAuthors] = useState<Author[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<number[]>([]);
  const [selectedAuthors, setSelectedAuthors] = useState<number[]>([]);
  const [recommendations, setRecommendations] = useState<Book[]>([]);
  
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const parentRef = useRef<HTMLDivElement>(null);

  const authAxios = axios.create({
    baseURL: API_BASE,
    headers: { Authorization: `Bearer ${token}` }
  });

  useEffect(() => {
    if (token) {
      fetchUser();
    }
    fetchCatalogData();
  }, [token]);

  const fetchCatalogData = async () => {
    try {
      const res = await axios.get(`${API_BASE}/books/`);
      const allBooks: Book[] = res.data;
      const genreMap = new Map();
      const authorMap = new Map();
      allBooks.forEach(b => {
        b.genres.forEach(g => genreMap.set(g.id, g));
        b.authors.forEach(a => authorMap.set(a.id, a));
      });
      setGenres(Array.from(genreMap.values()));
      setAuthors(Array.from(authorMap.values()));
    } catch (e) {
      console.error("Failed to fetch catalog");
    }
  };

  const fetchUser = async () => {
    try {
      const res = await authAxios.get('/users/me');
      setUser(res.data);
      if (res.data.preferred_genres.length === 0) {
        setView('onboarding');
      } else {
        setView('recommendations');
        fetchRecommendations();
      }
    } catch (e) {
      logout();
    }
  };

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (view === 'signup') {
        await axios.post(`${API_BASE}/signup`, { username, password });
        setView('login');
        alert("Account created! Please login.");
      } else {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        const res = await axios.post(`${API_BASE}/token`, formData);
        localStorage.setItem('token', res.data.access_token);
        setToken(res.data.access_token);
      }
    } catch (e: any) {
      setError(e.response?.data?.detail || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    setView('login');
  };

  const handlePreferences = async () => {
    setLoading(true);
    try {
      await authAxios.post('/users/preferences', {
        username: user.username,
        password: "", // Not used for update
        preferred_genre_ids: selectedGenres,
        preferred_author_ids: selectedAuthors
      });
      fetchUser();
    } catch (e) {
      setError("Failed to save preferences");
    } finally {
      setLoading(false);
    }
  };

  const fetchRecommendations = async () => {
    setLoading(true);
    try {
      const res = await authAxios.get('/recommendations/');
      setRecommendations(res.data);
    } catch (e) {
      setError("Failed to fetch recommendations");
    } finally {
      setLoading(false);
    }
  };

  const handleInteraction = async (bookId: number, type: 'like' | 'dislike') => {
    try {
      await authAxios.post('/interactions/', {
        book_id: bookId,
        interaction_type: type
      });
      const res = await authAxios.get('/recommendations/');
      setRecommendations(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const rowVirtualizer = useVirtualizer({
    count: recommendations.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 220,
    overscan: 5,
  });

  // ADA Helper: Screen reader announcements
  const [announcement, setAnnouncement] = useState('');

  if (view === 'login' || view === 'signup') {
    return (
      <main className="container animate-fade">
        <h1 className="title">{view === 'login' ? 'Welcome Back' : 'Create Account'}</h1>
        <p className="subtitle">Join our community of book lovers.</p>

        <form onSubmit={handleAuth} className="setup-section" aria-labelledby="auth-title">
          <div className="input-group">
            <label htmlFor="username">Username</label>
            <input 
              id="username"
              type="text" 
              required
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              aria-required="true"
            />
          </div>
          <div className="input-group">
            <label htmlFor="password">Password</label>
            <input 
              id="password"
              type="password" 
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-required="true"
            />
          </div>
          
          {error && <div role="alert" className="error-box">{error}</div>}

          <button type="submit" className="start-btn" disabled={loading}>
            {loading ? <Loader2 className="animate-spin" /> : view === 'login' ? 'Login' : 'Sign Up'}
          </button>
          
          <button 
            type="button" 
            className="text-btn" 
            onClick={() => setView(view === 'login' ? 'signup' : 'login')}
          >
            {view === 'login' ? "Don't have an account? Sign up" : "Already have an account? Login"}
          </button>
        </form>
      </main>
    );
  }

  if (view === 'onboarding') {
    return (
      <main className="container animate-fade">
        <h1 className="title">Personalize Your Feed</h1>
        <p className="subtitle">Pick at least one genre and author to get started.</p>

        <section aria-labelledby="genres-title">
          <h2 id="genres-title" className="section-title">Favorite Genres</h2>
          <div className="group" role="group" aria-label="Genre selection">
            {genres.map(g => (
              <button 
                key={g.id} 
                aria-pressed={selectedGenres.includes(g.id)}
                className={`chip ${selectedGenres.includes(g.id) ? 'active' : ''}`}
                onClick={() => setSelectedGenres(prev => 
                  prev.includes(g.id) ? prev.filter(id => id !== g.id) : [...prev, g.id]
                )}
              >
                {g.name}
              </button>
            ))}
          </div>
        </section>

        <section aria-labelledby="authors-title">
          <h2 id="authors-title" className="section-title">Favorite Authors</h2>
          <div className="group" role="group" aria-label="Author selection">
            {authors.map(a => (
              <button 
                key={a.id} 
                aria-pressed={selectedAuthors.includes(a.id)}
                className={`chip ${selectedAuthors.includes(a.id) ? 'active' : ''}`}
                onClick={() => setSelectedAuthors(prev => 
                  prev.includes(a.id) ? prev.filter(id => id !== a.id) : [...prev, a.id]
                )}
              >
                {a.name}
              </button>
            ))}
          </div>
        </section>

        <button className="start-btn" onClick={handlePreferences} disabled={loading || (selectedGenres.length === 0 && selectedAuthors.length === 0)}>
          {loading ? <Loader2 className="animate-spin" /> : "Save and Continue"}
        </button>
      </main>
    );
  }

  return (
    <main className="container animate-fade">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="title" style={{ textAlign: 'left' }}>Hi, {user?.username}</h1>
          <p className="subtitle" style={{ textAlign: 'left', marginBottom: '2rem' }}>Your personalized library awaits.</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button onClick={logout} className="chip" aria-label="Logout">
            <LogOut size={18} />
          </button>
          <Sparkles color="var(--primary)" size={32} aria-hidden="true" />
        </div>
      </header>

      <div aria-live="polite" className="sr-only">{announcement}</div>

      {loading ? (
        <div className="loading-overlay" aria-busy="true">
          <Loader2 className="animate-spin" size={40} color="var(--primary)" />
          <p>Curating your recommendations...</p>
        </div>
      ) : (
        <div 
          ref={parentRef} 
          className="list-viewport" 
          role="feed" 
          aria-busy={loading}
          aria-label="Recommended books"
        >
          <div 
            className="list-inner"
            style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const book = recommendations[virtualRow.index];
              return (
                <article
                  key={virtualRow.key}
                  className="book-card-container"
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  <div className="book-card">
                    <h3 className="book-title">{book.title}</h3>
                    <div className="book-author">by {book.authors.map(a => a.name).join(', ')}</div>
                    <p className="book-synopsis">{book.synopsis}</p>
                    <div className="book-actions">
                      <button 
                        className="btn-action btn-like" 
                        onClick={() => {
                          handleInteraction(book.id, 'like');
                          setAnnouncement(`Liked ${book.title}`);
                        }}
                        aria-label={`Like ${book.title}`}
                      >
                        <ThumbsUp size={16} aria-hidden="true" /> Relevant
                      </button>
                      <button 
                        className="btn-action btn-dislike" 
                        onClick={() => {
                          handleInteraction(book.id, 'dislike');
                          setAnnouncement(`Disliked ${book.title}`);
                        }}
                        aria-label={`Dislike ${book.title}`}
                      >
                        <ThumbsDown size={16} aria-hidden="true" /> Not for me
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </main>
  );
}

export default App;
