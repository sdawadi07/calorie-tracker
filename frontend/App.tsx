import { useEffect, useState } from 'react';
import {
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
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

function AppContent() {
  const [entries, setEntries] = useState<FoodEntry[]>([]);
  const [name, setName] = useState('');
  const [calories, setCalories] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const addEntry = async () => {
    const parsedCalories = parseInt(calories, 10);
    if (!name.trim() || Number.isNaN(parsedCalories)) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/log/quick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), calories: parsedCalories }),
      });
      const saved = await res.json();
      setEntries((prev) => [
        ...prev,
        { id: saved.id, name: saved.food.name, calories: saved.food.calories_per_100g },
      ]);
      setName('');
      setCalories('');
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
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <Text style={styles.title}>Today's Log</Text>
        <Text style={styles.total}>{totalCalories} kcal</Text>
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
              <Text style={styles.rowCalories}>{item.calories} kcal</Text>
            </TouchableOpacity>
          )}
        />

        <TextInput
          style={styles.input}
          placeholder="Food name"
          value={name}
          onChangeText={setName}
        />
        <TextInput
          style={styles.input}
          placeholder="Calories"
          value={calories}
          onChangeText={setCalories}
          keyboardType="numeric"
        />
        <TouchableOpacity style={styles.button} onPress={addEntry}>
          <Text style={styles.buttonText}>Add</Text>
        </TouchableOpacity>

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
  },
  rowCalories: {
    fontSize: 16,
    color: '#666',
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
    marginBottom: 16,
  },
  buttonText: {
    color: '#fff',
    fontWeight: '600',
  },
});
