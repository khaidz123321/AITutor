package re.edu.ai_elearning.service.impl;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import re.edu.ai_elearning.service.SseService;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

@Slf4j
@Service
public class SseServiceImpl implements SseService {

    private final Map<Long, List<SseEmitter>> userEmitters = new ConcurrentHashMap<>();

    @Override
    public SseEmitter subscribe(Long userId) {
        // Emitter timeout: 30 minutes
        SseEmitter emitter = new SseEmitter(1800_000L);

        userEmitters.computeIfAbsent(userId, k -> new CopyOnWriteArrayList<>()).add(emitter);

        emitter.onCompletion(() -> removeEmitter(userId, emitter));
        emitter.onTimeout(() -> removeEmitter(userId, emitter));
        emitter.onError((e) -> removeEmitter(userId, emitter));

        // Send initial connect success event to establish SSE connection successfully
        try {
            emitter.send(SseEmitter.event()
                    .name("connect")
                    .data("Connected successfully"));
        } catch (IOException e) {
            removeEmitter(userId, emitter);
        }

        return emitter;
    }

    @Override
    public void sendNotification(Long userId, Object notification) {
        List<SseEmitter> emitters = userEmitters.get(userId);
        if (emitters != null) {
            List<SseEmitter> deadEmitters = new ArrayList<>();
            for (SseEmitter emitter : emitters) {
                try {
                    emitter.send(SseEmitter.event()
                            .name("notification")
                            .data(notification));
                } catch (Exception e) {
                    deadEmitters.add(emitter);
                }
            }
            emitters.removeAll(deadEmitters);
            if (emitters.isEmpty()) {
                userEmitters.remove(userId);
            }
        }
    }

    @Override
    public void broadcastNotification(Object notification) {
        List<Long> deadUserIds = new ArrayList<>();
        userEmitters.forEach((userId, emitters) -> {
            List<SseEmitter> deadEmitters = new ArrayList<>();
            for (SseEmitter emitter : emitters) {
                try {
                    emitter.send(SseEmitter.event()
                            .name("notification")
                            .data(notification));
                } catch (Exception e) {
                    deadEmitters.add(emitter);
                }
            }
            emitters.removeAll(deadEmitters);
            if (emitters.isEmpty()) {
                deadUserIds.add(userId);
            }
        });
        deadUserIds.forEach(userEmitters::remove);
    }

    private void removeEmitter(Long userId, SseEmitter emitter) {
        List<SseEmitter> emitters = userEmitters.get(userId);
        if (emitters != null) {
            emitters.remove(emitter);
            if (emitters.isEmpty()) {
                userEmitters.remove(userId);
            }
        }
    }
}
