package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.SupportTicketRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.entity.SupportTicket;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.repository.SupportTicketRepository;

import java.util.List;

@RestController
@RequestMapping("/api/v1/support-tickets")
@RequiredArgsConstructor
public class SupportTicketController {

    private final SupportTicketRepository supportTicketRepository;

    @PostMapping
    public ResponseEntity<ApiResponse<SupportTicket>> createSupportTicket(@Valid @RequestBody SupportTicketRequest request) {
        SupportTicket ticket = SupportTicket.builder()
                .studentName(request.getStudentName())
                .studentEmail(request.getStudentEmail())
                .problemType(request.getProblemType())
                .message(request.getMessage())
                .status("PENDING")
                .build();

        SupportTicket saved = supportTicketRepository.save(ticket);
        return ResponseEntity.ok(ApiResponse.success("Gửi yêu cầu hỗ trợ thành công! Đội ngũ kỹ thuật sẽ phản hồi sớm nhất.", saved));
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<SupportTicket>>> getAllSupportTickets() {
        List<SupportTicket> list = supportTicketRepository.findAllByOrderByCreatedAtDesc();
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách yêu cầu hỗ trợ thành công", list));
    }

    @PatchMapping("/{id}/resolve")
    public ResponseEntity<ApiResponse<SupportTicket>> resolveSupportTicket(@PathVariable Long id) {
        SupportTicket ticket = supportTicketRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy yêu cầu hỗ trợ id: " + id));

        ticket.setStatus("RESOLVED");
        SupportTicket updated = supportTicketRepository.save(ticket);
        return ResponseEntity.ok(ApiResponse.success("Đã xử lý yêu cầu hỗ trợ thành công", updated));
    }
}
