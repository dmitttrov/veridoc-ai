import { BadRequestException } from '@nestjs/common';
import { AiClient, AiUpstreamError } from '../ai/ai.client';
import { RetrieveController } from './retrieve.controller';

describe('RetrieveController', () => {
  it('rejects an invalid request body', async () => {
    const ai = { retrieve: jest.fn() } as unknown as AiClient;
    const controller = new RetrieveController(ai);
    await expect(controller.retrieve({ query: '' })).rejects.toBeInstanceOf(
      BadRequestException,
    );
    expect(ai.retrieve).not.toHaveBeenCalled();
  });

  it('forwards a valid request and returns passages', async () => {
    const response = {
      query: 'revenue',
      passages: [],
      embeddingModel: 'm',
      embeddingDim: 384,
    };
    const ai = {
      retrieve: jest.fn().mockResolvedValue(response),
    } as unknown as AiClient;
    const controller = new RetrieveController(ai);

    const out = await controller.retrieve({ query: 'revenue' });
    expect(out).toBe(response);
    expect(ai.retrieve).toHaveBeenCalledWith(
      expect.objectContaining({ query: 'revenue', topK: 5 }),
    );
  });

  it('propagates an upstream 503', async () => {
    const ai = {
      retrieve: jest
        .fn()
        .mockRejectedValue(new AiUpstreamError(503, 'database_unavailable', 'down')),
    } as unknown as AiClient;
    const controller = new RetrieveController(ai);
    await expect(controller.retrieve({ query: 'revenue' })).rejects.toMatchObject({
      status: 503,
    });
  });
});
