import { useEffect, useState } from "react";
import { Alert, Image, Linking, Pressable, Text, View } from "react-native";
import { Screen } from "../components/Screen";
import { Card } from "../components/Card";
import { loadMessages } from "../api/endpoints";
import { API_BASE_URL } from "../api/config";
import { colors } from "../theme/tokens";

function attachmentLabel(attachment = {}) {
  return attachment.name || attachment.filename || attachment.url || "Attachment";
}

function attachmentUrl(attachment = {}) {
  const url = attachment.url || attachment.preview_url || attachment.previewUrl || "";
  if (!url || /^https?:\/\//i.test(url)) return url;
  return `${API_BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

function isImageAttachment(attachment = {}) {
  const contentType = String(attachment.content_type || attachment.contentType || attachment.type || "").toLowerCase();
  const label = attachmentLabel(attachment).toLowerCase();
  const url = attachmentUrl(attachment).toLowerCase().split("?")[0];
  return contentType.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(label) || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(url);
}

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
              {item.attachments.map((attachment, index) => {
                const url = attachmentUrl(attachment);
                const label = attachmentLabel(attachment);
                const isImage = url && isImageAttachment(attachment);
                return (
                  <Pressable key={`${url || label}-${index}`} onPress={() => url && Linking.openURL(url)}>
                    {isImage ? (
                      <Image
                        source={{ uri: url }}
                        accessibilityLabel={label}
                        style={{ width: "100%", height: 180, borderRadius: 10, backgroundColor: colors.border }}
                        resizeMode="cover"
                      />
                    ) : null}
                    <Text style={{ color: colors.primary, fontWeight: "800", marginTop: isImage ? 4 : 0 }}>{label}</Text>
                  </Pressable>
                );
              })}
            </View>
          ) : null}
        </Card>
      )) : <Text style={{ color: colors.muted }}>No messages found.</Text>}
    </Screen>
  );
}
