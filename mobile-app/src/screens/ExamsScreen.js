import { useEffect, useState } from "react";
import { Alert, Text } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { loadExams } from "../api/endpoints";
import { colors } from "../theme/tokens";

export function ExamsScreen() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    loadExams()
      .then((data) => setItems(data.exams || data.upcoming_exams || []))
      .catch((error) => Alert.alert("Exams unavailable", error.message));
  }, []);

  return (
    <Screen>
      <Text style={{ color: colors.text, fontSize: 28, fontWeight: "900" }}>Exams</Text>
      {items.length ? items.map((item) => (
        <Card key={String(item.id || item.title)}>
          <Text style={{ color: colors.textDark, fontWeight: "900" }}>{item.title || item.subject || "Exam"}</Text>
          <Text style={{ color: colors.mutedDark }}>{item.start_date || item.due_date || item.status || "Ready"}</Text>
        </Card>
      )) : <Text style={{ color: colors.muted }}>No exams found.</Text>}
    </Screen>
  );
}
