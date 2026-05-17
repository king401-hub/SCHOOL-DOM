import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";

export async function pickDocument() {
  return DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: false });
}

export async function takeProfilePhoto() {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (permission.status !== "granted") {
    throw new Error("Camera permission is required.");
  }
  return ImagePicker.launchCameraAsync({ allowsEditing: true, quality: 0.85 });
}
