#ifndef IO_HPP
#define IO_HPP

#include <cstdio>
#include <string>
#include <stdlib.h>
#include <assert.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>

constexpr int PAGESIZE = 1024 * 4;

class fastIO {
private:
    char *buffer, *S = nullptr, *T = nullptr;
    FILE * f;
	long bytes = 0;
    int sz;

public: 
    fastIO(FILE * f_) {
        f = f_;
        buffer = new char[PAGESIZE];
        sz = sizeof(char);
    }

    fastIO(const std::string &file, const std::string openStyle) {
        f = fopen(file.c_str(), openStyle.c_str());

        T = S = buffer = new char[PAGESIZE];

        if (openStyle[0] == 'r') bytes = file_size(file);

        sz = sizeof(char);
    }

    ~fastIO() {
        fclose(f);
        delete[] buffer;
    }

    bool empty() {

        while (true) {

            if (S == T) {
                if (bytes == 0) return true;

                if (bytes < PAGESIZE) {
                    T = (S = buffer) + fread(buffer, 1, bytes, f);
                    bytes = 0;
                } else {
                    T = (S = buffer) + fread(buffer, 1, PAGESIZE, f);
                    bytes -= PAGESIZE;
                }
            }
            while (S != T && (*S < '0' || *S > '9')) S++;

            if ('0' <= *S && *S <= '9') break;
        }

        return false;
    }

    char getChar() {

        if (S == T) {
            if (bytes == 0) return EOF;

            if (bytes < PAGESIZE) {
                T = (S = buffer) + fread(buffer, 1, bytes, f);
                bytes = 0;
            } else {
                T = (S = buffer) + fread(buffer, 1, PAGESIZE, f);
                bytes -= PAGESIZE;
            }

            if (S == T) return EOF;
        }

        return *S++;
    }

    void getInt(int & re) {
        char c;
        for (c = getChar(); c < '0' || c > '9'; c = getChar());
        while (c >= '0' && c <= '9') re = (re << 1) + (re << 3) + (c - '0'), c = getChar();
    }

    unsigned getUInt() {
        char c;
        unsigned re = 0;
        for (c = getChar(); c < '0' || c > '9'; c = getChar());
        while (c >= '0' && c <= '9') re = (re << 1) + (re << 3) + (c - '0'), c = getChar();
        return re;
    }

    void jump() {
        char c;
        unsigned re = 0;
        for (c = getChar(); c < '0' || c > '9'; c = getChar());
        while (c >= '0' && c <= '9') re = (re << 1) + (re << 3) + (c - '0'), c = getChar();
        if (c == '.') {
            c = getChar();
            while (c >= '0' && c <= '9') re = (re << 1) + (re << 3) + (c - '0'), c = getChar();
        }

    }

    void seek(uint32_t b) {
        assert(fseek(f, b, SEEK_SET) == 0);
    }

    static inline bool file_exists(std::string filename) {
        struct stat st;
        return stat(filename.c_str(), &st) == 0;
    }

    static inline long file_size(std::string filename) {
        struct stat st;
        assert(stat(filename.c_str(), &st) == 0);
        return st.st_size;
    }
};

#endif