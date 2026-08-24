import { useEffect, useState } from 'react';
import {
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  View,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';

// Your laptop's LAN IP so a phone on the same WiFi can reach the backend.
// Update this if your IP changes (e.g. after reconnecting to WiFi).
const API_BASE_URL = 'http://10.1.10.112:8000';

type FoodEntry = {
  id: number;
  name: string;
  calories: number;
};

type SearchResult = {
  name: string;
  calories_per_100g: number;
  protein_per_100g: number;
  carbs_per_100g: number;
  fat_per_100g: number;
};

type WeightEntry = {
  id: number;
  weight_kg: number;
  recorded_at: string;
};

function FoodLogScreen() {
  const [entries, setEntries] = useState<FoodEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [grams, setGrams] = useState('100');

  const [manualMode, setManualMode] = useState(false);
  const [manualName, setManualName] = useState('');
  const [manualCalories, setManualCalories] = useState('');

  const totalCalories = entries.reduce((sum, entry) => sum + entry.calories, 0);

  const loadTodaysLog = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/log/today`);
      const data = await res.json();
      setEntries(
        data.map((e: any) => ({
          id: e.id,
          name: e.food.name,
          calories: e.food.calories_per_100g,
        }))
      );
      setError(null);
    } catch (e) {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTodaysLog();
  }, []);

  const runSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSelected(null);
    try {
      const res = await fetch(`${API_BASE_URL}/foods/search?q=${encodeURIComponent(query.trim())}`);
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setError(body?.detail || 'Food search failed.');
        setResults([]);
        return;
      }
      setResults(await res.json());
      setError(null);
    } catch (e) {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setSearching(false);
    }
  };

  const addFromSearch = async () => {
    if (!selected) return;
    const parsedGrams = parseFloat(grams);
    if (Number.isNaN(parsedGrams) || parsedGrams <= 0) return;
    try {
      const res = await fetch(`${API_BASE_URL}/log/from_search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...selected, grams: parsedGrams }),
      });
      const saved = await res.json();
      setEntries((prev) => [
        ...prev,
        { id: saved.id, name: saved.food.name, calories: (saved.food.calories_per_100g * saved.grams) / 100 },
      ]);
      setSelected(null);
      setResults([]);
      setQuery('');
      setGrams('100');
      setError(null);
    } catch (e) {
      setError('Could not save. Is the backend running?');
    }
  };

  const addManually = async () => {
    const parsedCalories = parseInt(manualCalories, 10);
    if (!manualName.trim() || Number.isNaN(parsedCalories)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/log/quick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: manualName.trim(), calories: parsedCalories }),
      });
      const saved = await res.json();
      setEntries((prev) => [
        ...prev,
        { id: saved.id, name: saved.food.name, calories: saved.food.calories_per_100g },
      ]);
      setManualName('');
      setManualCalories('');
      setManualMode(false);
      setError(null);
    } catch (e) {
      setError('Could not save. Is the backend running?');
    }
  };

  const removeEntry = async (id: number) => {
    setEntries((prev) => prev.filter((entry) => entry.id !== id));
    try {
      await fetch(`${API_BASE_URL}/log/${id}`, { method: 'DELETE' });
    } catch (e) {
      setError('Could not delete on the server.');
    }
  };

  return (
    <>
      <Text style={styles.title}>Today's Log</Text>
      <Text style={styles.total}>{Math.round(totalCalories)} kcal</Text>
      {error && <Text style={styles.error}>{error}</Text>}

      <FlatList
        style={styles.list}
        data={entries}
        keyExtractor={(item) => item.id.toString()}
        refreshing={loading}
        onRefresh={loadTodaysLog}
        ListEmptyComponent={<Text style={styles.empty}>No food logged yet.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onLongPress={() => removeEntry(item.id)}>
            <Text style={styles.rowName}>{item.name}</Text>
            <Text style={styles.rowCalories}>{Math.round(item.calories)} kcal</Text>
          </TouchableOpacity>
        )}
      />

      {!manualMode && (
        <>
          <Text style={styles.sectionLabel}>Search food</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g. banana"
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={runSearch}
            returnKeyType="search"
          />
          <TouchableOpacity style={styles.button} onPress={runSearch} disabled={searching}>
            <Text style={styles.buttonText}>{searching ? 'Searching…' : 'Search'}</Text>
          </TouchableOpacity>

          {results.length > 0 && !selected && (
            <FlatList
              style={styles.results}
              data={results}
              keyExtractor={(item, index) => `${item.name}-${index}`}
              renderItem={({ item }) => (
                <TouchableOpacity style={styles.row} onPress={() => setSelected(item)}>
                  <Text style={styles.rowName}>{item.name}</Text>
                  <Text style={styles.rowCalories}>{Math.round(item.calories_per_100g)} kcal/100g</Text>
                </TouchableOpacity>
              )}
            />
          )}

          {selected && (
            <>
              <Text style={styles.sectionLabel}>
                {selected.name} — {Math.round(selected.calories_per_100g)} kcal/100g
              </Text>
              <TextInput
                style={styles.input}
                placeholder="Grams eaten"
                value={grams}
                onChangeText={setGrams}
                keyboardType="numeric"
              />
              <TouchableOpacity style={styles.button} onPress={addFromSearch}>
                <Text style={styles.buttonText}>Add to log</Text>
              </TouchableOpacity>
            </>
          )}

          <TouchableOpacity onPress={() => setManualMode(true)}>
            <Text style={styles.link}>Can't find it? Enter manually</Text>
          </TouchableOpacity>
        </>
      )}

      {manualMode && (
        <>
          <TextInput
            style={styles.input}
            placeholder="Food name"
            value={manualName}
            onChangeText={setManualName}
          />
          <TextInput
            style={styles.input}
            placeholder="Total calories"
            value={manualCalories}
            onChangeText={setManualCalories}
            keyboardType="numeric"
          />
          <TouchableOpacity style={styles.button} onPress={addManually}>
            <Text style={styles.buttonText}>Add</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setManualMode(false)}>
            <Text style={styles.link}>Back to search</Text>
          </TouchableOpacity>
        </>
      )}
    </>
  );
}

function WeightScreen() {
  const [weights, setWeights] = useState<WeightEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [weightInput, setWeightInput] = useState('');

  const loadWeights = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/weight/`);
      setWeights(await res.json());
      setError(null);
    } catch (e) {
      setError('Could not reach the server. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWeights();
  }, []);

  const logWeight = async () => {
    const parsed = parseFloat(weightInput);
    if (Number.isNaN(parsed) || parsed <= 0) return;
    try {
      const res = await fetch(`${API_BASE_URL}/weight/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weight_kg: parsed }),
      });
      const saved = await res.json();
      setWeights((prev) => [saved, ...prev]);
      setWeightInput('');
      setError(null);
    } catch (e) {
      setError('Could not save. Is the backend running?');
    }
  };

  const latest = weights[0];

  return (
    <>
      <Text style={styles.title}>Weight</Text>
      <Text style={styles.total}>{latest ? `${latest.weight_kg} kg (latest)` : 'No entries yet'}</Text>
      {error && <Text style={styles.error}>{error}</Text>}

      <FlatList
        style={styles.list}
        data={weights}
        keyExtractor={(item) => item.id.toString()}
        refreshing={loading}
        onRefresh={loadWeights}
        ListEmptyComponent={<Text style={styles.empty}>No weight logged yet.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row}>
            <Text style={styles.rowName}>{item.recorded_at}</Text>
            <Text style={styles.rowCalories}>{item.weight_kg} kg</Text>
          </TouchableOpacity>
        )}
      />

      <TextInput
        style={styles.input}
        placeholder="Weight (kg)"
        value={weightInput}
        onChangeText={setWeightInput}
        keyboardType="numeric"
      />
      <TouchableOpacity style={styles.button} onPress={logWeight}>
        <Text style={styles.buttonText}>Log weight</Text>
      </TouchableOpacity>
    </>
  );
}

function AppContent() {
  const [tab, setTab] = useState<'log' | 'weight'>('log');

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.tabs}>
          <TouchableOpacity
            style={[styles.tabButton, tab === 'log' && styles.tabButtonActive]}
            onPress={() => setTab('log')}
          >
            <Text style={[styles.tabButtonText, tab === 'log' && styles.tabButtonTextActive]}>Food Log</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabButton, tab === 'weight' && styles.tabButtonActive]}
            onPress={() => setTab('weight')}
          >
            <Text style={[styles.tabButtonText, tab === 'weight' && styles.tabButtonTextActive]}>Weight</Text>
          </TouchableOpacity>
        </View>

        {tab === 'log' ? <FoodLogScreen /> : <WeightScreen />}

        <StatusBar style="auto" />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppContent />
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  flex: {
    flex: 1,
    paddingHorizontal: 20,
  },
  tabs: {
    flexDirection: 'row',
    marginTop: 12,
    marginBottom: 4,
    backgroundColor: '#f0f0f0',
    borderRadius: 8,
    padding: 4,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 6,
    alignItems: 'center',
  },
  tabButtonActive: {
    backgroundColor: '#000',
  },
  tabButtonText: {
    color: '#666',
    fontWeight: '600',
  },
  tabButtonTextActive: {
    color: '#fff',
  },
  title: {
    fontSize: 24,
    fontWeight: '600',
    marginTop: 12,
  },
  total: {
    fontSize: 16,
    color: '#666',
    marginBottom: 12,
  },
  error: {
    color: '#c00',
    marginBottom: 12,
  },
  list: {
    flex: 1,
  },
  results: {
    maxHeight: 200,
    marginBottom: 8,
  },
  empty: {
    color: '#999',
    marginTop: 20,
    textAlign: 'center',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  rowName: {
    fontSize: 16,
    flexShrink: 1,
    paddingRight: 8,
  },
  rowCalories: {
    fontSize: 16,
    color: '#666',
  },
  sectionLabel: {
    fontSize: 14,
    color: '#444',
    fontWeight: '600',
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 8,
  },
  button: {
    backgroundColor: '#000',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
    marginBottom: 8,
  },
  buttonText: {
    color: '#fff',
    fontWeight: '600',
  },
  link: {
    color: '#666',
    textAlign: 'center',
    marginBottom: 16,
    textDecorationLine: 'underline',
  },
});
