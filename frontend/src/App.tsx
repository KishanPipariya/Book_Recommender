import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ThumbsUp, ThumbsDown, Loader2, Sparkles, BookOpen, ArrowRight } from 'lucide-react';
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
  const [user, setUser] = useState<{ id: number; username: string } | null>(null);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [authors, setAuthors] = useState<Author[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<number[]>([]);
  const [selectedAuthors, setSelectedAuthors] = useState<number[]>([]);
  const [recommendations, setRecommendations] = useState<Book[]>([]);
  const [loading, setLoading] = useState(false);
  const [username, setUsername] = useState('');
  const [error, setError] = useState<string | null>(null);

  const parentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const booksRes = await axios.get(`${API_BASE}/books/`);
        const allBooks: Book[] = booksRes.data;
        
        const genreMap = new Map<number, Genre>();
        const authorMap = new Map<number, Author>();
        
        allBooks.forEach(b => {
          b.genres.forEach(g => genreMap.set(g.id, g));
          b.authors.forEach(a => authorMap.set(a.id, a));
        });

        setGenres(Array.from(genreMap.values()));
        setAuthors(Array.from(authorMap.values()));
      } catch (e: any) {
        setError("Failed to connect to backend. Make sure it is running.");
      }
    };
    fetchData();
  }, []);

  const handleInitialize = async () => {
    if (!username) return alert("Please enter a username");
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/users/`, {
        username,
        preferred_genre_ids: selectedGenres,
        preferred_author_ids: selectedAuthors
      });
      setUser(res.data);
      // Fetch recommendations immediately
      const recsRes = await axios.get(`${API_BASE}/recommendations/${res.data.id}`);
      setRecommendations(recsRes.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || "Something went wrong. Check API Key.");
    } finally {
      setLoading(false);
    }
  };

  const handleInteraction = async (bookId: number, type: 'like' | 'dislike') => {
    if (!user) return;
    try {
      await axios.post(`${API_BASE}/interactions/?user_id=${user.id}`, {
        book_id: bookId,
        interaction_type: type
      });
      // Refresh without full loading state for better UX
      const res = await axios.get(`${API_BASE}/recommendations/${user.id}`);
      setRecommendations(res.data);
    } catch (e) {
      console.error("Failed to record interaction", e);
    }
  };

  const rowVirtualizer = useVirtualizer({
    count: recommendations.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 220,
    overscan: 5,
  });

  if (!user) {
    return (
      <div className="container animate-fade">
        <h1 className="title">Book Recommender</h1>
        <p className="subtitle">Tell us what you like, and we'll find your next favorite read.</p>
        
        {error && <div style={{ color: 'var(--danger)', marginBottom: '1.5rem', textAlign: 'center', background: '#fff1f2', padding: '1rem', borderRadius: '12px' }}>{error}</div>}
        
        <div className="setup-section">
          <div className="section-title">Your Identity</div>
          <input 
            type="text" 
            placeholder="What should we call you?" 
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          
          <div className="section-title">Favorite Genres</div>
          <div className="group">
            {genres.map(g => (
              <div 
                key={g.id} 
                className={`chip ${selectedGenres.includes(g.id) ? 'active' : ''}`}
                onClick={() => setSelectedGenres(prev => 
                  prev.includes(g.id) ? prev.filter(id => id !== g.id) : [...prev, g.id]
                )}
              >
                {g.name}
              </div>
            ))}
          </div>

          <div className="section-title">Favorite Authors</div>
          <div className="group">
            {authors.map(a => (
              <div 
                key={a.id} 
                className={`chip ${selectedAuthors.includes(a.id) ? 'active' : ''}`}
                onClick={() => setSelectedAuthors(prev => 
                  prev.includes(a.id) ? prev.filter(id => id !== a.id) : [...prev, a.id]
                )}
              >
                {a.name}
              </div>
            ))}
          </div>

          <button className="start-btn" onClick={handleInitialize} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" /> : <>Get Recommendations <ArrowRight size={20} /></>}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container animate-fade">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="title" style={{ textAlign: 'left' }}>For you, {user.username}</h1>
          <p className="subtitle" style={{ textAlign: 'left', marginBottom: '2rem' }}>Personalized picks from your library.</p>
        </div>
        <Sparkles color="var(--primary)" size={32} />
      </div>

      {error && <div style={{ color: 'var(--danger)', marginBottom: '1.5rem', textAlign: 'center' }}>{error}</div>}
      
      {loading ? (
        <div className="loading-overlay">
          <Loader2 className="animate-spin" size={40} color="var(--primary)" />
          <p>Analyzing your preferences...</p>
        </div>
      ) : (
        <div ref={parentRef} className="list-viewport">
          <div 
            className="list-inner"
            style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const book = recommendations[virtualRow.index];
              return (
                <div
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
                      <button className="btn-action btn-like" onClick={() => handleInteraction(book.id, 'like')}>
                        <ThumbsUp size={16} /> Relevant
                      </button>
                      <button className="btn-action btn-dislike" onClick={() => handleInteraction(book.id, 'dislike')}>
                        <ThumbsDown size={16} /> Not for me
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      
      {!loading && recommendations.length === 0 && (
        <div className="loading-overlay">
          <BookOpen size={48} color="var(--border)" />
          <p>No matches found. Try broadening your preferences!</p>
        </div>
      )}
    </div>
  );
}

export default App;
