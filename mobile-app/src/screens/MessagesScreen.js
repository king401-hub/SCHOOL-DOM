import { useEffect, useState } from "react";
import { Alert, Linking, Pressable, Text, View } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { loadMessages } from "../api/endpoints";
import { colors } from "../theme/tokens";

export function MessagesScreen() {
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    loadMessages()
      .then((data) => setMessages(data.messages || data.inbox || []))
      .catch((error) => Alert.alert("Messages unavailable", error.message));
  }, []);

  return (
    <Screen>
      <Text style={{ color: colors.text, fontSize: 28, fontWeight: "900" }}>Messages</Text>
      {messages.length ? messages.map((item) => (
        <Card key={String(item.id || item.created_at)}>
          <Text style={{ color: colors.textDark, fontWeight: "900" }}>{item.subject || item.title || "Message"}</Text>
          <Text style={{ color: colors.mutedDark }}>{item.body || item.message || ""}</Text>
          {Array.isArray(item.attachments) && item.attachments.length ? (
            <View style={{ marginTop: 10, gap: 6 }}>
              {item.attachments.map((attachment, index) => (
                <Pressable key={`${attachment.url || attachment.name}-${index}`} onPress={() => attachment.url && Linking.openURL(attachment.url)}>
                  <Text style={{ color: colors.primary, fontWeight: "800" }}>{attachment.name || "Attachment"}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </Card>
      )) : <Text style={{ color: colors.muted }}>No messages found.</Text>}
    </Screen>
  );
}
