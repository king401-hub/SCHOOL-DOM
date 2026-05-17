import * as BackgroundFetch from "expo-background-fetch";
import * as TaskManager from "expo-task-manager";
import { replayOfflineQueue } from "../api/client";

const TASK_NAME = "schooldom-background-sync";

TaskManager.defineTask(TASK_NAME, async () => {
  try {
    await replayOfflineQueue();
    return BackgroundFetch.BackgroundFetchResult.NewData;
  } catch {
    return BackgroundFetch.BackgroundFetchResult.Failed;
  }
});

export async function registerBackgroundSync() {
  const registered = await TaskManager.isTaskRegisteredAsync(TASK_NAME);
  if (registered) return;
  await BackgroundFetch.registerTaskAsync(TASK_NAME, {
    minimumInterval: 15 * 60,
    stopOnTerminate: false,
    startOnBoot: true,
  }).catch(() => {});
}
