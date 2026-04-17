import { Button, Typography } from "@humansignal/ui";
import { Space } from "@humansignal/ui/lib/space/space";
import { Block } from "apps/labelstudio/src/components/Menu/MenuContext";
import { Modal } from "apps/labelstudio/src/components/Modal/ModalPopup";
import { API } from "apps/labelstudio/src/providers/ApiProvider";
import { useCallback, useEffect, useRef, useState } from "react";
import { useToast } from "@humansignal/ui";
import { Input } from "../../../components/Form";

export function CreateOrganizationModal({
  opened,
  onOpened,
  onClosed,
  onSuccess,
}: {
  opened: boolean;
  onOpened?: () => void;
  onClosed?: () => void;
  onSuccess?: (org: { id: number; title: string }) => void;
}) {
  const modalRef = useRef<Modal>();
  useEffect(() => {
    if (modalRef.current && opened) {
      modalRef.current?.show?.();
    } else if (modalRef.current && modalRef.current.visible) {
      modalRef.current?.hide?.();
    }
  }, [opened]);

  return (
    <Modal
      ref={modalRef}
      title="Create Organization"
      opened={opened}
      bareFooter={true}
      body={<CreateOrgForm onSuccess={onSuccess} onClosed={onClosed} />}
      footer={null}
      style={{ width: 480 }}
      onHide={onClosed}
      onShow={onOpened}
    />
  );
}

const CreateOrgForm = ({
  onSuccess,
  onClosed,
}: {
  onSuccess?: (org: { id: number; title: string }) => void;
  onClosed?: () => void;
}) => {
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const handleSubmit = useCallback(async () => {
    if (!title.trim()) {
      setError("Organization title is required");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await API.invoke("createOrganization", {}, { body: { title: title.trim() } });
      toast.show({ message: `Organization "${result.title}" created successfully` });
      setTitle("");
      onSuccess?.(result);
      onClosed?.();
    } catch (err: any) {
      const errorMessage = err?.message || err?.detail || "Failed to create organization";
      setError(errorMessage);
      if (err?.status === 403) {
        setError("Only superusers can create organizations");
      }
    } finally {
      setLoading(false);
    }
  }, [title, onSuccess, onClosed, toast]);

  return (
    <Block name="create-org">
      <div className="mb-4">
        <label className="mb-2 block text-base font-medium">Organization Title</label>
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Enter organization title"
          style={{ width: "100%" }}
          disabled={loading}
        />
      </div>

      {error && (
        <Typography size="small" className="text-danger-default mb-4">
          {error}
        </Typography>
      )}

      <Typography size="small" className="text-neutral-content-subtler mb-4">
        Create a new organization. Only superusers can create organizations.
      </Typography>

      <Space spread>
        <Button variant="default" look="outlined" onClick={onClosed} disabled={loading} aria-label="Cancel">
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={handleSubmit}
          disabled={loading || !title.trim()}
          aria-label="Create organization"
        >
          {loading ? "Creating..." : "Create"}
        </Button>
      </Space>
    </Block>
  );
};
