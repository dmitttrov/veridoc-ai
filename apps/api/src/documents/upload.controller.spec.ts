import { BadRequestException, HttpException } from '@nestjs/common';
import { AiClient, AiUpstreamError } from '../ai/ai.client';
import { UploadController } from './upload.controller';

function pdfFile(): Express.Multer.File {
  return {
    fieldname: 'file',
    originalname: 'acme.pdf',
    encoding: '7bit',
    mimetype: 'application/pdf',
    size: 1024,
    buffer: Buffer.from('%PDF-1.4'),
    stream: undefined as never,
    destination: '',
    filename: '',
    path: '',
  } as Express.Multer.File;
}

describe('UploadController', () => {
  it('rejects a missing file', async () => {
    const ai = { ingestDocument: jest.fn() } as unknown as AiClient;
    const controller = new UploadController(ai);
    await expect(controller.upload(undefined)).rejects.toBeInstanceOf(BadRequestException);
    expect(ai.ingestDocument).not.toHaveBeenCalled();
  });

  it('rejects a non-PDF content type with 415', async () => {
    const ai = { ingestDocument: jest.fn() } as unknown as AiClient;
    const controller = new UploadController(ai);
    const file = { ...pdfFile(), mimetype: 'image/png' } as Express.Multer.File;

    await expect(controller.upload(file)).rejects.toMatchObject({ status: 415 });
    expect(ai.ingestDocument).not.toHaveBeenCalled();
  });

  it('forwards a valid PDF and returns the ingestion result', async () => {
    const result = { documentId: 'id', state: 'succeeded', alreadyIngested: false };
    const ai = {
      ingestDocument: jest.fn().mockResolvedValue(result),
    } as unknown as AiClient;
    const controller = new UploadController(ai);

    const out = await controller.upload(pdfFile());
    expect(out).toBe(result);
    expect(ai.ingestDocument).toHaveBeenCalledWith(
      expect.any(Buffer),
      'acme.pdf',
      'application/pdf',
    );
  });

  it('propagates an upstream error with its status and code', async () => {
    const ai = {
      ingestDocument: jest
        .fn()
        .mockRejectedValue(new AiUpstreamError(422, 'pdf_encrypted', 'Encrypted PDFs are not accepted.')),
    } as unknown as AiClient;
    const controller = new UploadController(ai);

    await expect(controller.upload(pdfFile())).rejects.toMatchObject({ status: 422 });
    try {
      await controller.upload(pdfFile());
    } catch (err) {
      expect((err as HttpException).getResponse()).toMatchObject({ code: 'pdf_encrypted' });
    }
  });

  it('maps a transport failure to 503', async () => {
    const ai = {
      ingestDocument: jest.fn().mockRejectedValue(new Error('ECONNREFUSED')),
    } as unknown as AiClient;
    const controller = new UploadController(ai);
    await expect(controller.upload(pdfFile())).rejects.toMatchObject({ status: 503 });
  });
});
