import { Alert, Badge, Button, FileButton, Group, Loader, Text, Title } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  IconAlertCircle,
  IconFileText,
  IconUpload,
} from "@tabler/icons-react";
import { api, type StudyDocument } from "../../api/client";
import styles from "./DocumentsPanel.module.css";

const STATUS_COLORS: Record<StudyDocument["status"], string> = {
  processing: "yellow",
  indexed: "teal",
  failed: "red",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  planId: number;
}

export default function DocumentsPanel({ planId }: Props) {
  const qc = useQueryClient();

  const { data: documents = [], isLoading } = useQuery<StudyDocument[]>({
    queryKey: ["documents", planId],
    queryFn: () => api.getDocuments(planId),
    enabled: !!planId,
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDocument(planId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents", planId] });
    },
  });

  return (
    <section className={styles.section}>
      <Group justify="space-between" mb="lg">
        <Title order={4} className={styles.title}>
          Documents
        </Title>
        <FileButton
          onChange={(file) => file && upload.mutate(file)}
          accept="application/pdf,text/plain,text/markdown,.pdf,.txt,.md"
        >
          {(props) => (
            <Button
              {...props}
              leftSection={<IconUpload size={13} />}
              color="cyan"
              size="xs"
              variant="light"
              loading={upload.isPending}
            >
              Upload document
            </Button>
          )}
        </FileButton>
      </Group>

      {upload.isError && (
        <Alert
          icon={<IconAlertCircle size={16} />}
          color="red"
          variant="light"
          mb="md"
          withCloseButton
          onClose={() => upload.reset()}
        >
          Couldn't upload that file. Use a PDF, TXT, or Markdown file with
          readable text.
        </Alert>
      )}

      {isLoading ? (
        <div className={styles.loader}>
          <Loader color="cyan" size="sm" />
        </div>
      ) : documents.length === 0 ? (
        <div className={styles.empty}>
          <IconFileText size={32} stroke={1.2} color="var(--c-cool-gray)" />
          <Text className={styles.emptyText}>
            Upload PDFs or notes to ask questions about your study materials.
          </Text>
        </div>
      ) : (
        <div className={styles.list}>
          {documents.map((doc) => (
            <div key={doc.id} className={styles.row}>
              <IconFileText size={18} color="var(--c-turquoise)" />
              <div className={styles.rowMain}>
                <Text className={styles.filename}>{doc.filename}</Text>
                <Text className={styles.meta}>
                  {formatSize(doc.size_bytes)}
                  {doc.status === "indexed" && ` · ${doc.num_chunks} chunks`}
                </Text>
              </div>
              <Badge
                color={STATUS_COLORS[doc.status]}
                variant="light"
                size="sm"
              >
                {doc.status}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
