import { useEffect, useState } from "react";
import { Alert, Text } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { loadResults } from "../api/endpoints";
import { colors } from "../theme/tokens";

export function ResultsScreen() {
  const [results, setResults] = useState([]);

  useEffect(() => {
    loadResults()
      .then((data) => setResults(data.results || data.report_card?.subjects || []))
      .catch((error) => Alert.alert("Results unavailable", error.message));
  }, []);

  return (
    <Screen>
      <Text style={{ color: colors.text, fontSize: 28, fontWeight: "900" }}>Results</Text>
      {results.length ? results.map((item) => (
        <Card key={String(item.id || item.subject || item.name)}>
          <Text style={{ color: colors.textDark, fontWeight: "900" }}>{item.subject || item.name || "Subject"}</Text>
          <Text style={{ color: colors.mutedDark }}>{item.score ?? item.total ?? item.grade ?? "Pending"}</Text>
        </Card>
      )) : <Text style={{ color: colors.muted }}>No results found.</Text>}
    </Screen>
  );
}
