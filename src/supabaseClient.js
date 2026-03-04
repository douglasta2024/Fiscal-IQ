import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'placeholder';

// Create the client
// If the user hasn't set their credentials yet, we provide dummy values
// so the UI doesn't crash, but auth calls will fail.
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
